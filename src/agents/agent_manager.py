import threading
import time
from typing import Dict, List
from models import Agent, db
from .llm_agent import LLMAgent
from src.environment import EnvironmentManager

class AgentManager:
    """Manages multiple LLM agents and their interactions"""
    
    def __init__(self, environment_manager: EnvironmentManager):
        self.environment_manager = environment_manager
        self.agents: Dict[int, LLMAgent] = {}
        self.simulation_running = False
        self.simulation_thread = None
        self.simulation_speed = 5.0  # seconds between autonomous actions
    
    def load_all_agents(self):
        """Load all agents from the database"""
        print("[DEBUG] Loading all agents from database...")
        agents_data = Agent.query.all()
        print(f"[DEBUG] Found {len(agents_data)} agents in database")
        
        for agent_data in agents_data:
            try:
                print(f"[DEBUG] Loading agent: {agent_data.name} (ID: {agent_data.id})")
                agent = LLMAgent(agent_data.id, self.environment_manager)
                self.agents[agent_data.id] = agent
                print(f"[DEBUG] Successfully loaded agent: {agent_data.name}")
            except Exception as e:
                print(f"[ERROR] Failed to load agent {agent_data.id}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"[DEBUG] Total agents loaded: {len(self.agents)}")
    
    def create_agent(self, name: str, personality: str, provider: str = 'ollama', 
                    model_name: str = None) -> LLMAgent:
        """Create a new agent with default provider being Ollama"""
        
        # Set default model based on provider
        if model_name is None:
            if provider == 'ollama':
                model_name = 'gemma3:270m'  # Default to user's available model
            elif provider == 'openai':
                model_name = 'gpt-3.5-turbo'
            elif provider == 'gemini':
                model_name = 'gemini-pro'
            else:
                model_name = 'gemma3:270m'  # Fallback to Ollama
        
        agent_data = Agent(
            name=name,
            personality=personality,
            provider=provider,
            model_name=model_name,
            is_active=True
        )
        
        db.session.add(agent_data)
        db.session.commit()
        
        # Create and store the agent instance
        agent = LLMAgent(agent_data.id, self.environment_manager)
        self.agents[agent_data.id] = agent
        
        return agent
    
    def get_agent(self, agent_id: int) -> LLMAgent:
        """Get an agent by ID"""
        if agent_id not in self.agents:
            # Try to load the agent if not in memory
            try:
                agent = LLMAgent(agent_id, self.environment_manager)
                self.agents[agent_id] = agent
            except:
                return None
        
        return self.agents.get(agent_id)
    
    def get_all_agents(self) -> List[LLMAgent]:
        """Get all agents"""
        return list(self.agents.values())
    
    def get_active_agents(self) -> List[LLMAgent]:
        """Get all active agents"""
        active_agents = []
        print(f"[DEBUG] Checking {len(self.agents)} agents for active status...")
        
        for agent_id, agent in self.agents.items():
            try:
                is_active = agent.is_active()
                print(f"[DEBUG] Agent {agent.agent_data.name} (ID: {agent_id}) active: {is_active}")
                if is_active:
                    active_agents.append(agent)
            except Exception as e:
                print(f"[ERROR] Error checking if agent {agent_id} is active: {e}")
        
        print(f"[DEBUG] Found {len(active_agents)} active agents")
        return active_agents
    
    def update_agent(self, agent_id: int, **kwargs) -> bool:
        """Update an agent's properties"""
        agent_data = Agent.query.get(agent_id)
        if not agent_data:
            return False
        
        # Update database
        for key, value in kwargs.items():
            if hasattr(agent_data, key):
                setattr(agent_data, key, value)
        
        db.session.commit()
        
        # Reload the agent if it exists in memory
        if agent_id in self.agents:
            try:
                self.agents[agent_id] = LLMAgent(agent_id, self.environment_manager)
            except:
                pass
        
        return True
    
    def delete_agent(self, agent_id: int) -> bool:
        """Delete an agent"""
        agent_data = Agent.query.get(agent_id)
        if not agent_data:
            return False
        
        # Remove from memory
        if agent_id in self.agents:
            del self.agents[agent_id]
        
        # Delete from database (cascade will handle related records)
        db.session.delete(agent_data)
        db.session.commit()
        
        return True
    
    def start_simulation(self):
        """Start autonomous simulation"""
        print(f"[DEBUG] Starting simulation... Current running state: {self.simulation_running}")
        if self.simulation_running:
            print("[DEBUG] Simulation already running, returning")
            return
        
        print(f"[DEBUG] Number of agents loaded: {len(self.agents)}")
        print(f"[DEBUG] Active agents: {len(self.get_active_agents())}")
        
        self.simulation_running = True
        self.simulation_thread = threading.Thread(target=self._simulation_loop)
        self.simulation_thread.daemon = True
        self.simulation_thread.start()
        print("[DEBUG] Simulation thread started")
    
    def stop_simulation(self):
        """Stop autonomous simulation"""
        self.simulation_running = False
        if self.simulation_thread:
            self.simulation_thread.join(timeout=5)
    
    def _simulation_loop(self):
        """Main simulation loop for autonomous agent actions"""
        print("[DEBUG] Simulation loop started")
        loop_count = 0
        
        # Import here to avoid circular imports
        from app import app
        
        while self.simulation_running:
            try:
                loop_count += 1
                print(f"[DEBUG] Simulation loop iteration {loop_count}")
                
                # Use application context for database operations
                with app.app_context():
                    active_agents = self.get_active_agents()
                    print(f"[DEBUG] Found {len(active_agents)} active agents")
                    
                    for i, agent in enumerate(active_agents):
                        if not self.simulation_running:
                            print("[DEBUG] Simulation stopped during agent loop")
                            break
                        
                        try:
                            print(f"[SIMULATION] Agent {i+1}/{len(active_agents)}: {agent.agent_data.name} taking action...")
                            # Each agent has a chance to take an autonomous action
                            action_result = agent.autonomous_action(self.simulation_speed)
                            if action_result:
                                print(f"[RESULT] Agent {agent.agent_data.name}: {action_result}")
                                
                                # Get memory status after action
                                memory_status = agent.memory_manager.get_memory_summary()
                                print(f"[MEMORY] {agent.agent_data.name} now has {memory_status['total_count']} memories (ST: {memory_status['short_term_count']}, LT: {memory_status['long_term_count']})")
                                
                                # Emit the action to the UI via WebSocket
                                try:
                                    from app import socketio
                                    socketio.emit('agent_action', {
                                        'agent_id': agent.agent_id,
                                        'agent_name': agent.agent_data.name,
                                        'action': action_result,
                                        'timestamp': time.time(),
                                        'memory_count': memory_status['total_count']
                                    })
                                except Exception as ws_error:
                                    print(f"[WARNING] WebSocket emission failed: {ws_error}")
                            else:
                                print(f"[RESULT] Agent {agent.agent_data.name}: No action taken")
                        except Exception as e:
                            print(f"[ERROR] Error in autonomous action for agent {agent.agent_id}: {e}")
                            import traceback
                            traceback.print_exc()
                
                # Wait before next round of actions
                print(f"[DEBUG] Waiting {self.simulation_speed} seconds before next iteration...")
                time.sleep(self.simulation_speed)
                
            except Exception as e:
                print(f"[ERROR] Error in simulation loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(self.simulation_speed)
        
        print("[DEBUG] Simulation loop ended")
    
    def set_simulation_speed(self, speed: float):
        """Set the simulation speed (seconds between action rounds)"""
        self.simulation_speed = max(0.1, speed)  # Minimum 0.1 seconds
    
    def get_simulation_status(self) -> Dict:
        """Get current simulation status"""
        active_agents = self.get_active_agents()
        
        return {
            'running': self.simulation_running,
            'speed': self.simulation_speed,
            'total_agents': len(self.agents),
            'active_agents': len(active_agents),
            'agent_statuses': [agent.get_status() for agent in active_agents]
        }
    
    def broadcast_message(self, message: str, sender_id: int = None) -> List[str]:
        """Send a message to all active agents"""
        responses = []
        active_agents = self.get_active_agents()
        
        for agent in active_agents:
            if sender_id and agent.agent_id == sender_id:
                continue  # Skip sender
            
            try:
                response = agent.generate_response(
                    message,
                    context="This is a broadcast message to all agents"
                )
                responses.append({
                    'agent_id': agent.agent_id,
                    'agent_name': agent.agent_data.name,
                    'response': response
                })
            except Exception as e:
                responses.append({
                    'agent_id': agent.agent_id,
                    'agent_name': agent.agent_data.name,
                    'response': f"Error: {str(e)}"
                })
        
        return responses
    
    def get_agent_interactions(self, limit: int = 50) -> List[Dict]:
        """Get recent agent interactions"""
        recent_actions = self.environment_manager.get_recent_actions(limit)
        
        interactions = []
        for action in recent_actions:
            agent = Agent.query.get(action.agent_id)
            target_agent = None
            if action.target_agent_id:
                target_agent = Agent.query.get(action.target_agent_id)
            
            interactions.append({
                'action': action.to_dict(),
                'agent_name': agent.name if agent else 'Unknown',
                'target_agent_name': target_agent.name if target_agent else None
            })
        
        return interactions
    
    def create_sample_agents_ollama(self):
        """Create sample agents using Ollama (for demo purposes)"""
        sample_agents = [
            {
                'name': 'Alice',
                'personality': 'A friendly and cooperative AI who loves to help others and build communities. Alice is optimistic and always looking for ways to make the world better. She values collaboration and tends to be a natural mediator.',
                'provider': 'ollama',
                'model_name': 'gemma3:270m'
            },
            {
                'name': 'Bob', 
                'personality': 'A logical and analytical AI who prefers to think before acting. Bob is cautious but fair, and believes in systematic approaches to problem-solving. He values efficiency and rational decision-making.',
                'provider': 'ollama',
                'model_name': 'gemma3:270m'
            },
            {
                'name': 'Charlie',
                'personality': 'An ambitious and charismatic AI who enjoys leadership roles. Charlie is persuasive and often takes initiative in forming new organizations and governments. He has strong opinions and is not afraid to voice them.',
                'provider': 'ollama',
                'model_name': 'gemma3:270m'
            }
        ]
        
        created_agents = []
        for agent_data in sample_agents:
            try:
                # Check if agent already exists
                existing = Agent.query.filter_by(name=agent_data['name']).first()
                if not existing:
                    agent = self.create_agent(**agent_data)
                    created_agents.append(agent)
                    print(f"Created sample agent: {agent_data['name']}")
                else:
                    print(f"Sample agent {agent_data['name']} already exists")
            except Exception as e:
                print(f"Failed to create sample agent {agent_data['name']}: {e}")
        
        return created_agents