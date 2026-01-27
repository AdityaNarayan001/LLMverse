from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
from config import Config
from models import db, Agent, Character, CharacterState, Belief, Evolution, GodMessage, Simulation, Environment, Action, Memory
from src.agents import AgentManager
from src.environment import EnvironmentManager
from src.providers.factory import ProviderFactory
from src.utils.logger import get_logger, get_websocket_handler, WebSocketHandler
import json
import os
import random
from datetime import datetime, timedelta
import threading
import time
from collections import deque

app = Flask(__name__)
app.config.from_object(Config)

# Initialize logger
logger = get_logger(__name__)

# Ensure log directory exists
if not os.path.exists('logs'):
    os.makedirs('logs')

# Initialize extensions
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Connect WebSocket handler to emit logs in real-time
WebSocketHandler.set_socketio(socketio)

# Initialize managers
environment_manager = EnvironmentManager()
agent_manager = AgentManager(environment_manager)

def initialize_app():
    """Initialize database tables and load initial data"""
    logger.info("Starting app initialization")
    with app.app_context():
        logger.info("Creating database tables")
        db.create_all()
        
        logger.info("Loading existing agents")
        # Load existing agents
        agent_manager.load_all_agents()
        
        # Create sample agents if none exist
        all_agents = agent_manager.get_all_agents()
        logger.info(f"Found {len(all_agents)} agents after loading")
        
        if not all_agents:
            logger.info("No agents found, creating sample agents")
            agent_manager.create_sample_agents_ollama()
        else:
            logger.info("Agents already exist, skipping sample creation")
    
    logger.info("App initialization complete")

# Remove the old create_sample_agents function as it's now in AgentManager

# Routes
@app.route('/')
def index():
    """Main dashboard"""
    agents = Agent.query.all()
    # Get fresh environment from database to avoid DetachedInstanceError
    environment = Environment.query.filter_by(is_active=True).first()
    simulation_status = agent_manager.get_simulation_status()
    
    return render_template('index.html', 
                         agents=agents,
                         environment=environment,
                         simulation_status=simulation_status)

@app.route('/agents')
def agents_page():
    """Agents management page"""
    agents = Agent.query.all()
    providers = ProviderFactory.get_available_providers()
    
    # Get available models for each provider
    provider_models = {}
    for provider in providers:
        try:
            p = ProviderFactory.create_provider(provider)
            if p.is_available():
                provider_models[provider] = p.list_models()
            else:
                provider_models[provider] = []
        except:
            provider_models[provider] = []
    
    return render_template('agents.html', 
                         agents=agents,
                         providers=providers,
                         provider_models=provider_models)

@app.route('/environment')
def environment_page():
    """Environment management page"""
    environments = Environment.query.all()
    # Get fresh current environment from database to avoid DetachedInstanceError
    current_env = Environment.query.filter_by(is_active=True).first()
    env_state = environment_manager.get_environment_state()
    env_rules = environment_manager.get_environment_rules()
    
    return render_template('environment.html',
                         environments=environments,
                         current_environment=current_env,
                         environment_state=env_state,
                         environment_rules=env_rules)

@app.route('/interactions')
def interactions_page():
    """Interactions and history page"""
    interactions = agent_manager.get_agent_interactions(100)
    return render_template('interactions.html', interactions=interactions)

@app.route('/chat')
def chat_page():
    """Chat interface with agents"""
    agents = Agent.query.filter_by(is_active=True).all()
    return render_template('chat.html', agents=agents)

# API Routes
@app.route('/api/agents', methods=['GET'])
def get_agents():
    """Get all agents"""
    agents = Agent.query.all()
    return jsonify([agent.to_dict() for agent in agents])

@app.route('/api/agents', methods=['POST'])
def create_agent():
    """Create a new agent"""
    data = request.json
    
    try:
        agent = agent_manager.create_agent(
            name=data['name'],
            personality=data['personality'],
            provider=data['provider'],
            model_name=data['model_name']
        )
        
        # Emit update to connected clients
        socketio.emit('agent_created', agent.get_status())
        
        return jsonify(agent.get_status()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/agents/<int:agent_id>', methods=['PUT'])
def update_agent(agent_id):
    """Update an agent"""
    data = request.json
    
    try:
        success = agent_manager.update_agent(agent_id, **data)
        if success:
            agent = agent_manager.get_agent(agent_id)
            status = agent.get_status() if agent else None
            
            # Emit update to connected clients
            socketio.emit('agent_updated', status)
            
            return jsonify(status)
        else:
            return jsonify({'error': 'Agent not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/agents/<int:agent_id>', methods=['DELETE'])
def delete_agent(agent_id):
    """Delete an agent"""
    try:
        success = agent_manager.delete_agent(agent_id)
        if success:
            # Emit update to connected clients
            socketio.emit('agent_deleted', {'agent_id': agent_id})
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Agent not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/agents/<int:agent_id>/chat', methods=['POST'])
def chat_with_agent(agent_id):
    """Chat with a specific agent"""
    data = request.json
    message = data.get('message', '')
    
    try:
        agent = agent_manager.get_agent(agent_id)
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404
        
        response = agent.generate_response(message)
        
        # Emit the interaction to connected clients
        socketio.emit('agent_interaction', {
            'agent_id': agent_id,
            'agent_name': agent.agent_data.name,
            'message': message,
            'response': response
        })
        
        return jsonify({
            'agent_id': agent_id,
            'agent_name': agent.agent_data.name,
            'response': response
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/agents/<int:agent_id>/memories', methods=['GET'])
def get_agent_memories(agent_id):
    """Get agent's memories (short-term and long-term)"""
    try:
        agent = agent_manager.get_agent(agent_id)
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404
        
        # Get memories from the memory manager
        short_term_memories = agent.memory_manager.get_memories(memory_type='short_term')
        long_term_memories = agent.memory_manager.get_memories(memory_type='long_term')
        memory_summary = agent.memory_manager.get_memory_summary()
        
        # Convert to JSON-serializable format
        def memory_to_dict(memory):
            return {
                'id': memory.id,
                'content': memory.content,
                'importance_score': memory.importance_score,
                'created_at': memory.created_at.isoformat(),
                'expires_at': memory.expires_at.isoformat() if memory.expires_at else None
            }
        
        return jsonify({
            'agent_id': agent_id,
            'agent_name': agent.agent_data.name,
            'short_term_memories': [memory_to_dict(m) for m in short_term_memories],
            'long_term_memories': [memory_to_dict(m) for m in long_term_memories],
            'total_count': memory_summary['total_count'],
            'short_term_count': memory_summary['short_term_count'],
            'long_term_count': memory_summary['long_term_count']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/simulation/start', methods=['POST'])
def start_simulation():
    """Start the autonomous simulation"""
    logger.info("API: Starting simulation requested")
    try:
        agent_manager.start_simulation()
        status = agent_manager.get_simulation_status()
        logger.info(f"Simulation started", extra={'context': {'running': status.get('running'), 'agents': status.get('active_agents')}})
        
        # Emit update to connected clients
        socketio.emit('simulation_started', status)
        
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error starting simulation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 400

@app.route('/api/simulation/stop', methods=['POST'])
def stop_simulation():
    """Stop the autonomous simulation"""
    try:
        agent_manager.stop_simulation()
        status = agent_manager.get_simulation_status()
        
        # Emit update to connected clients
        socketio.emit('simulation_stopped', status)
        
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/simulation/status', methods=['GET'])
def get_simulation_status():
    """Get current simulation status"""
    return jsonify(agent_manager.get_simulation_status())

@app.route('/api/simulation/speed', methods=['POST'])
def update_simulation_speed():
    """Update simulation speed"""
    try:
        data = request.get_json()
        speed = float(data.get('speed', 5.0))
        
        # Validate speed range
        if speed < 0.5 or speed > 10.0:
            return jsonify({'error': 'Speed must be between 0.5 and 10.0 seconds'}), 400
        
        # Update speed in agent manager
        agent_manager.set_simulation_speed(speed)
        
        return jsonify({'success': True, 'speed': speed})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/environment/reset', methods=['POST'])
def reset_environment():
    """Reset the environment to initial state"""
    try:
        environment_manager.reset_environment()
        
        # Emit update to connected clients
        socketio.emit('environment_reset', {
            'state': environment_manager.get_environment_state(),
            'rules': environment_manager.get_environment_rules()
        })
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/environment/rules', methods=['PUT'])
def update_environment_rules():
    """Update environment rules"""
    try:
        data = request.json
        
        # Get current environment
        current_env = Environment.query.filter_by(is_active=True).first()
        if not current_env:
            return jsonify({'error': 'No active environment found'}), 404
        
        # Update rules
        import json
        current_rules = json.loads(current_env.rules) if current_env.rules else {}
        current_rules.update(data)
        current_env.rules = json.dumps(current_rules)
        current_env.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Emit update to connected clients
        socketio.emit('environment_rules_updated', {
            'rules': current_rules
        })
        
        return jsonify({'success': True, 'rules': current_rules})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/agents/<int:agent_id>/memories', methods=['DELETE'])
def delete_agent_memories(agent_id):
    """Delete all memories for an agent"""
    try:
        agent = agent_manager.get_agent(agent_id)
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404
        
        # Delete all memories for this agent
        Memory.query.filter_by(character_id=agent_id).delete()
        db.session.commit()
        
        # Emit update to connected clients
        socketio.emit('agent_memories_cleared', {'agent_id': agent_id})
        
        return jsonify({'success': True, 'message': f'All memories deleted for agent {agent.agent_data.name}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/environment/switch/<int:env_id>', methods=['POST'])
def switch_environment(env_id):
    """Switch to a different environment"""
    try:
        success = environment_manager.switch_environment(env_id)
        if success:
            # Get fresh environment from database to avoid DetachedInstanceError
            current_env = Environment.query.filter_by(is_active=True).first()
            # Emit update to connected clients
            socketio.emit('environment_switched', {
                'environment': current_env.to_dict() if current_env else None,
                'state': environment_manager.get_environment_state(),
                'rules': environment_manager.get_environment_rules()
            })
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Environment not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/interactions', methods=['GET'])
def get_interactions():
    """Get recent interactions"""
    limit = request.args.get('limit', 50, type=int)
    interactions = agent_manager.get_agent_interactions(limit)
    return jsonify(interactions)


# ==========================================
# V2 Routes - New Game-like Interface
# ==========================================

@app.route('/v2/')
@app.route('/v2/welcome')
def welcome():
    """V2 Welcome page"""
    characters = Character.query.all()
    providers = [{'name': p} for p in ProviderFactory.get_available_providers()]
    simulation = Simulation.query.first()
    
    return render_template('v2/welcome.html',
                         characters=characters,
                         providers=providers,
                         simulation_running=simulation.is_running if simulation else False)


@app.route('/v2/create')
def create_character_page():
    """V2 Character creation page"""
    characters = Character.query.all()
    providers = [{'name': p} for p in ProviderFactory.get_available_providers()]
    
    # Get available models for each provider
    provider_models = {}
    for p in ProviderFactory.get_available_providers():
        try:
            provider = ProviderFactory.create_provider(p)
            if provider.is_available():
                models = provider.list_models()
                # Normalize model format
                provider_models[p] = [{'name': m if isinstance(m, str) else m.get('name', str(m))} for m in models]
            else:
                provider_models[p] = []
        except:
            provider_models[p] = []
    
    return render_template('v2/create.html',
                         characters=characters,
                         providers=providers,
                         provider_models=provider_models)


@app.route('/v2/god-mode')
def god_mode():
    """V2 God Mode - Main simulation view"""
    characters = Character.query.filter_by(is_active=True).all()
    simulation = Simulation.query.first()
    
    if not simulation:
        simulation = Simulation(name='LLMverse', is_running=False, day=1, speed=5.0)
        db.session.add(simulation)
        db.session.commit()
    
    return render_template('v2/god_mode.html',
                         characters=characters,
                         simulation=simulation)


@app.route('/v2/profile/<int:character_id>')
def character_profile(character_id):
    """V2 Character profile page"""
    character = Character.query.get_or_404(character_id)
    state = CharacterState.query.filter_by(character_id=character_id).first()
    beliefs = Belief.query.filter_by(character_id=character_id).all()
    evolutions = Evolution.query.filter_by(character_id=character_id).order_by(Evolution.created_at.desc()).all()
    
    # Count conversations
    conversation_count = Action.query.filter_by(
        character_id=character_id,
        action_type='conversation'
    ).count()
    
    return render_template('v2/profile.html',
                         character=character,
                         state=state,
                         beliefs=beliefs,
                         evolutions=evolutions,
                         conversation_count=conversation_count)


# ==========================================
# V2 API Routes
# ==========================================

@app.route('/api/v2/characters', methods=['GET'])
def api_v2_get_characters():
    """Get all characters with their state"""
    characters = Character.query.all()
    result = []
    for char in characters:
        data = char.to_dict(include_state=True)
        data['beliefs'] = [b.to_dict() for b in char.beliefs] if char.beliefs else []
        result.append(data)
    return jsonify(result)


@app.route('/api/v2/characters', methods=['POST'])
def api_v2_create_character():
    """Create a new character"""
    data = request.json
    
    try:
        # Create character
        character = Character(
            name=data['name'],
            avatar=data.get('avatar', '🧑'),
            core_personality=data['core_personality'],
            provider=data['provider'],
            model_name=data['model_name'],
            is_active=True
        )
        db.session.add(character)
        db.session.flush()  # Get the ID
        
        # Create initial state with traits
        initial_traits = data.get('initial_traits', {})
        state = CharacterState(
            character_id=character.id,
            trait_curiosity=initial_traits.get('curiosity', 50),
            trait_empathy=initial_traits.get('empathy', 50),
            trait_assertiveness=initial_traits.get('assertiveness', 50),
            trait_creativity=initial_traits.get('creativity', 50),
            trait_trust=initial_traits.get('trust', 50),
            trait_optimism=initial_traits.get('optimism', 50),
            emotional_state='neutral',
            energy_level=100
        )
        db.session.add(state)
        db.session.commit()
        
        logger.info(f"Created character: {character.name}")
        socketio.emit('character_created', character.to_dict(include_state=True))
        
        return jsonify(character.to_dict(include_state=True)), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating character: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/v2/characters/<int:char_id>', methods=['GET'])
def api_v2_get_character(char_id):
    """Get a single character with full details"""
    character = Character.query.get_or_404(char_id)
    data = character.to_dict(include_state=True)
    data['beliefs'] = [b.to_dict() for b in character.beliefs] if character.beliefs else []
    data['evolutions'] = [e.to_dict() for e in character.evolutions] if character.evolutions else []
    return jsonify(data)


@app.route('/api/v2/characters/<int:char_id>', methods=['DELETE'])
def api_v2_delete_character(char_id):
    """Delete a character"""
    character = Character.query.get_or_404(char_id)
    name = character.name
    
    try:
        db.session.delete(character)
        db.session.commit()
        logger.info(f"Deleted character: {name}")
        socketio.emit('character_deleted', {'id': char_id, 'name': name})
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@app.route('/api/v2/characters/<int:char_id>/logs', methods=['GET'])
def api_v2_get_character_logs(char_id):
    """Get full conversation logs for a character"""
    character = Character.query.get_or_404(char_id)
    
    # Get all actions involving this character
    actions = Action.query.filter(
        (Action.character_id == char_id) | (Action.target_character_id == char_id)
    ).order_by(Action.created_at.desc()).limit(100).all()
    
    logs = [{
        'type': a.action_type,
        'content': a.description,
        'timestamp': a.created_at.isoformat() if a.created_at else None
    } for a in actions]
    
    return jsonify(logs)


@app.route('/api/v2/characters/<int:char_id>/reset', methods=['POST'])
def api_v2_reset_character(char_id):
    """Reset character evolution (restore original traits)"""
    character = Character.query.get_or_404(char_id)
    state = CharacterState.query.filter_by(character_id=char_id).first()
    
    if state:
        state.trait_curiosity = 50
        state.trait_empathy = 50
        state.trait_assertiveness = 50
        state.trait_creativity = 50
        state.trait_trust = 50
        state.trait_optimism = 50
        state.conversations_since_evolution = 0
        db.session.commit()
        
        logger.info(f"Reset evolution for character: {character.name}")
        return jsonify({'success': True})
    
    return jsonify({'error': 'Character state not found'}), 404


@app.route('/api/v2/characters/generate-random', methods=['POST'])
def api_v2_generate_random_characters():
    """Generate random characters"""
    data = request.json
    count = data.get('count', 2)
    
    # Random character templates
    templates = [
        {'name': 'Luna', 'avatar': '🌙', 'personality': 'Dreamy and introspective. Loves philosophy and asking deep questions about existence. Tends to see beauty in everything.'},
        {'name': 'Rex', 'avatar': '🦊', 'personality': 'Curious and adventurous. Always eager to explore new ideas. Has a playful sense of humor but can be surprisingly wise.'},
        {'name': 'Nova', 'avatar': '⭐', 'personality': 'Energetic and optimistic. Believes in the best of everyone. Natural leader who inspires others with enthusiasm.'},
        {'name': 'Sage', 'avatar': '🧙', 'personality': 'Thoughtful and measured. Values wisdom over haste. Enjoys teaching and helping others grow.'},
        {'name': 'Echo', 'avatar': '🎭', 'personality': 'Creative and expressive. Sees the world through artistic lens. Empathetic and deeply feels others emotions.'},
        {'name': 'Bolt', 'avatar': '⚡', 'personality': 'Quick-witted and decisive. Loves efficiency and getting things done. Can be impatient but means well.'},
    ]
    
    # Get available provider and model
    providers = ProviderFactory.get_available_providers()
    if not providers:
        return jsonify({'error': 'No providers available'}), 400
    
    default_provider = 'ollama' if 'ollama' in providers else providers[0]
    default_model = 'gemma3:27b'  # Default model
    
    try:
        provider = ProviderFactory.create_provider(default_provider)
        if provider.is_available():
            models = provider.list_models()
            if models:
                default_model = models[0] if isinstance(models[0], str) else models[0].get('name', default_model)
    except:
        pass
    
    created = []
    random.shuffle(templates)
    
    for template in templates[:count]:
        # Check if name already exists
        if Character.query.filter_by(name=template['name']).first():
            continue
        
        try:
            character = Character(
                name=template['name'],
                avatar=template['avatar'],
                core_personality=template['personality'],
                provider=default_provider,
                model_name=default_model,
                is_active=True
            )
            db.session.add(character)
            db.session.flush()
            
            # Random traits
            state = CharacterState(
                character_id=character.id,
                trait_curiosity=random.randint(30, 80),
                trait_empathy=random.randint(30, 80),
                trait_assertiveness=random.randint(30, 80),
                trait_creativity=random.randint(30, 80),
                trait_trust=random.randint(30, 80),
                trait_optimism=random.randint(30, 80),
                emotional_state='neutral',
                energy_level=100
            )
            db.session.add(state)
            created.append(character.to_dict())
        except Exception as e:
            logger.error(f"Error creating random character: {e}")
            continue
    
    db.session.commit()
    logger.info(f"Generated {len(created)} random characters")
    
    return jsonify(created), 201


@app.route('/api/v2/god/message', methods=['POST'])
def api_v2_god_message():
    """Send a God message to characters"""
    data = request.json
    message = data.get('message', '')
    mode = data.get('mode', 'broadcast')  # 'broadcast' or 'whisper'
    target_id = data.get('target_id')
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    if mode == 'whisper' and not target_id:
        return jsonify({'error': 'Target ID required for whisper'}), 400
    
    try:
        # Store the message
        god_msg = GodMessage(
            message_type=mode,
            content=message,
            target_character_id=target_id if mode == 'whisper' else None
        )
        db.session.add(god_msg)
        db.session.commit()
        
        # Emit to clients - God messages appear as consciousness injection
        socketio.emit('god_message', {
            'id': god_msg.id,
            'mode': mode,
            'content': message,
            'target_id': target_id,
            'timestamp': god_msg.created_at.isoformat()
        })
        
        logger.info(f"God message sent: {mode} - {message[:50]}...")
        return jsonify({'success': True, 'id': god_msg.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@app.route('/api/v2/simulation/start', methods=['POST'])
def api_v2_start_simulation():
    """Start the V2 simulation"""
    simulation = Simulation.query.first()
    if not simulation:
        simulation = Simulation(name='LLMverse', is_running=False, day=1, speed=5.0)
        db.session.add(simulation)
    
    simulation.is_running = True
    db.session.commit()
    
    # Start the actual simulation loop
    agent_manager.start_simulation()
    
    socketio.emit('simulation_update', {
        'running': True,
        'day': simulation.day
    })
    
    logger.info("V2 Simulation started")
    return jsonify({'success': True, 'running': True})


@app.route('/api/v2/simulation/stop', methods=['POST'])
def api_v2_stop_simulation():
    """Stop the V2 simulation"""
    simulation = Simulation.query.first()
    if simulation:
        simulation.is_running = False
        db.session.commit()
    
    agent_manager.stop_simulation()
    
    socketio.emit('simulation_update', {'running': False})
    
    logger.info("V2 Simulation stopped")
    return jsonify({'success': True, 'running': False})


@app.route('/api/v2/simulation/speed', methods=['POST'])
def api_v2_update_speed():
    """Update simulation speed"""
    data = request.json
    speed = float(data.get('speed', 1.0))
    
    simulation = Simulation.query.first()
    if simulation:
        simulation.speed = speed
        db.session.commit()
    
    agent_manager.set_simulation_speed(speed * 5)  # Convert multiplier to seconds
    
    return jsonify({'success': True, 'speed': speed})


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get recent system logs"""
    limit = request.args.get('limit', 100, type=int)
    ws_handler = get_websocket_handler()
    logs = ws_handler.get_recent_logs(limit)
    return jsonify(logs)


@app.route('/api/broadcast', methods=['POST'])
def broadcast_message():
    """Broadcast a message to all active agents"""
    data = request.json
    message = data.get('message', '')
    
    try:
        responses = agent_manager.broadcast_message(message)
        
        # Emit the broadcast to connected clients
        socketio.emit('broadcast_sent', {
            'message': message,
            'responses': responses
        })
        
        return jsonify(responses)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit('connected', {'status': 'Connected to LLMverse'})

@socketio.on('request_status')
def handle_status_request():
    """Handle status update request"""
    status = agent_manager.get_simulation_status()
    emit('status_update', status)

if __name__ == '__main__':
    logger.info("Starting LLMverse application")
    initialize_app()
    logger.info("Starting SocketIO server on http://0.0.0.0:5000")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)