from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
from config import Config
from models import db, Agent, Environment, Action, Memory
from src.agents import AgentManager
from src.environment import EnvironmentManager
from src.providers.factory import ProviderFactory
from src.utils.logger import get_logger, get_websocket_handler, WebSocketHandler
import json
import os
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
        Memory.query.filter_by(agent_id=agent_id).delete()
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