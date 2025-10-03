import threading
import time
import random
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
        self.current_agent_index = 0  # For round-robin scheduling
        self.communication_queue = []  # Track who should talk to whom
        self.last_speaker = None  # Track last speaker to avoid immediate repetition
    
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
        """Main simulation loop for autonomous agent actions with round-robin scheduling"""
        print("[DEBUG] Simulation loop started with round-robin scheduling")
        loop_count = 0
        conversation_topics = ["politics", "education", "community", "leadership", "society", "learning"]
        current_topic_index = 0
        
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
                    
                    if len(active_agents) < 2:
                        print("[DEBUG] Need at least 2 agents for conversation, waiting...")
                        time.sleep(self.simulation_speed)
                        continue
                    
                    # Round-robin scheduling: pick next agent in rotation
                    if self.current_agent_index >= len(active_agents):
                        self.current_agent_index = 0
                        current_topic_index = (current_topic_index + 1) % len(conversation_topics)
                        print(f"[TOPIC] Switching to topic: {conversation_topics[current_topic_index]}")
                    
                    current_agent = active_agents[self.current_agent_index]
                    print(f"[ROUND-ROBIN] Turn {loop_count}: {current_agent.agent_data.name}")
                    
                    # Find a target agent (prefer someone who hasn't been the last speaker)
                    other_agents = [a for a in active_agents if a.agent_id != current_agent.agent_id]
                    
                    if self.last_speaker:
                        # Try to find someone other than the last speaker
                        non_last_speakers = [a for a in other_agents if a.agent_id != self.last_speaker]
                        if non_last_speakers:
                            other_agents = non_last_speakers
                    
                    if other_agents:
                        target_agent = other_agents[loop_count % len(other_agents)]
                        current_topic = conversation_topics[current_topic_index]
                        
                        # Generate a focused conversation based on current topic
                        message = self._generate_topic_focused_message(
                            current_agent, target_agent, current_topic
                        )
                        
                        print(f"[CONVERSATION] {current_agent.agent_data.name} → {target_agent.agent_data.name}")
                        print(f"[TOPIC] {current_topic}: {message[:60]}...")
                        
                        # Send the message
                        current_agent.communicate_with_agent(target_agent.agent_id, message, self.simulation_speed)
                        
                        # Store memory about the interaction
                        memory_status = current_agent.memory_manager.get_memory_summary()
                        
                        # Emit the action to the UI
                        try:
                            from app import socketio
                            socketio.emit('agent_action', {
                                'agent_id': current_agent.agent_id,
                                'agent_name': current_agent.agent_data.name,
                                'action': f"Said to {target_agent.agent_data.name}: {message[:50]}...",
                                'timestamp': time.time(),
                                'memory_count': memory_status['total_count']
                            })
                        except Exception as ws_error:
                            print(f"[WARNING] WebSocket emission failed: {ws_error}")
                        
                        # Generate a response from the target agent (50% chance to avoid too much chatter)
                        if random.random() < 0.7:  # 70% chance to respond
                            response = self._generate_response_to_message(
                                target_agent, current_agent, message, current_topic
                            )
                            if response:
                                print(f"[RESPONSE] {target_agent.agent_data.name} responded: {response[:60]}...")
                                
                                # Emit the response
                                try:
                                    socketio.emit('agent_action', {
                                        'agent_id': target_agent.agent_id,
                                        'agent_name': target_agent.agent_data.name,
                                        'action': f"Replied to {current_agent.agent_data.name}: {response[:50]}...",
                                        'timestamp': time.time(),
                                        'memory_count': target_agent.memory_manager.get_memory_summary()['total_count']
                                    })
                                except Exception as ws_error:
                                    print(f"[WARNING] WebSocket emission failed for response: {ws_error}")
                        
                        self.last_speaker = current_agent.agent_id
                    
                    # Move to next agent in round-robin
                    self.current_agent_index = (self.current_agent_index + 1) % len(active_agents)
                
                # Wait before next round of actions
                print(f"[DEBUG] Waiting {self.simulation_speed} seconds before next turn...")
                time.sleep(self.simulation_speed)
                
            except Exception as e:
                print(f"[ERROR] Error in simulation loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(self.simulation_speed)
        
        print("[DEBUG] Simulation loop ended")
    
    def _get_agent_by_name(self, name: str) -> LLMAgent:
        """Get an agent by name"""
        for agent in self.agents.values():
            if agent.agent_data and agent.agent_data.name == name:
                return agent
        return None
    
    def _generate_topic_focused_message(self, sender: LLMAgent, target: LLMAgent, topic: str) -> str:
        """Generate a focused message based on the current conversation topic"""
        sender_personality = sender.agent_data.personality.lower()
        target_name = target.agent_data.name
        
        # Topic-specific conversation starters
        if topic == "politics":
            if "politics" in sender_personality or "governance" in sender_personality:
                messages = [
                    f"Hey {target_name}, I've been thinking about our community structure. What's your take on how decisions should be made?",
                    f"{target_name}, do you think we need better organization around here? I have some ideas.",
                    f"Hi {target_name}, what's your perspective on leadership styles? I'm curious about your thoughts.",
                    f"{target_name}, I believe collaboration is key to good governance. How do you see it?"
                ]
            else:
                messages = [
                    f"Hi {target_name}, what do you think about how things are organized around here?",
                    f"{target_name}, I'm curious about your views on community decisions - any thoughts?",
                    f"Hey {target_name}, do you have opinions about how we should work together?",
                    f"{target_name}, what's your take on making our community better?"
                ]
        
        elif topic == "education":
            if "teacher" in sender_personality or "education" in sender_personality:
                messages = [
                    f"Hello {target_name}, I love sharing knowledge! What's something you'd like to learn about?",
                    f"{target_name}, I think we can all teach each other. What's your area of expertise?",
                    f"Hi {target_name}, what's the most important lesson you've learned recently?",
                    f"{target_name}, I believe education shapes everything. What's your learning philosophy?"
                ]
            else:
                messages = [
                    f"Hi {target_name}, what's something interesting you've learned lately?",
                    f"{target_name}, I'm always curious about different perspectives. What's yours on learning?",
                    f"Hey {target_name}, what knowledge do you think is most valuable?",
                    f"{target_name}, what would you want to teach others if you could?"
                ]
        
        elif topic == "community":
            if "social" in sender_personality or "gossip" in sender_personality:
                messages = [
                    f"Hey {target_name}! I love how we're all connecting here. What do you think makes a good community?",
                    f"{target_name}, I'm always interested in how people get along. What's your secret?",
                    f"Hi {target_name}! What do you think brings people together best?",
                    f"{target_name}, community spirit is so important! How do you contribute to it?"
                ]
            else:
                messages = [
                    f"Hi {target_name}, what makes you feel most connected to others here?",
                    f"{target_name}, how do you think we can build stronger relationships?",
                    f"Hey {target_name}, what's your ideal vision for our community?",
                    f"{target_name}, what role do you see yourself playing in our group?"
                ]
        
        elif topic == "leadership":
            messages = [
                f"Hi {target_name}, what qualities do you think make a good leader?",
                f"{target_name}, I'm curious about your leadership style - how do you motivate others?",
                f"Hey {target_name}, what's your take on shared vs individual leadership?",
                f"{target_name}, how do you think leaders should handle disagreements?"
            ]
        
        elif topic == "society":
            messages = [
                f"Hi {target_name}, what kind of society do you think we're building here?",
                f"{target_name}, what values should guide how we live together?",
                f"Hey {target_name}, how do you envision our ideal social structure?",
                f"{target_name}, what traditions or customs should we develop?"
            ]
        
        else:  # learning
            messages = [
                f"Hi {target_name}, what's the most valuable thing you've discovered about yourself lately?",
                f"{target_name}, I'm always growing and changing. How about you?",
                f"Hey {target_name}, what challenges have helped you learn the most?",
                f"{target_name}, what wisdom would you share with others?"
            ]
        
        # Get recent conversation history to avoid repetition
        recent_memories = sender.memory_manager.get_memories(limit=10)
        recent_with_target = [m for m in recent_memories if target_name in m.content]
        
        # Choose message based on history to avoid repetition
        hash_seed = len(recent_with_target) + hash(target_name + topic)
        return messages[hash_seed % len(messages)]
    
    def _generate_response_to_message(self, responder: LLMAgent, sender: LLMAgent, 
                                    original_message: str, topic: str) -> str:
        """Generate a natural response to a message within the current topic"""
        try:
            responder_personality = responder.agent_data.personality.lower()
            sender_name = sender.agent_data.name
            
            # Create a contextual response prompt
            response_prompt = f"""{sender_name} just said to you: "{original_message}"
            
The conversation topic is {topic}. Respond naturally as {responder.agent_data.name} would, staying on topic but being conversational."""
            
            response = responder.generate_response(response_prompt)
            
            # Clean up any meta-commentary
            if "I should respond" in response or "I will say" in response or "My response" in response:
                # Generate a personality-based fallback
                if "gossip" in responder_personality or "social" in responder_personality:
                    fallbacks = [
                        f"That's really interesting, {sender_name}! I love hearing different perspectives.",
                        f"Oh {sender_name}, you always have such thoughtful ideas!",
                        f"Thanks for sharing that, {sender_name}. It gives me a lot to think about!",
                        f"I appreciate you bringing that up, {sender_name}. What else are you thinking about?"
                    ]
                elif "politics" in responder_personality or "governance" in responder_personality:
                    fallbacks = [
                        f"You raise excellent points, {sender_name}. I think we could build on that idea.",
                        f"That's a valuable perspective, {sender_name}. How do you think we could implement it?",
                        f"I appreciate your thoughtful approach, {sender_name}. Collaboration is key.",
                        f"Great insight, {sender_name}. I believe we can work together on this."
                    ]
                elif "teacher" in responder_personality or "education" in responder_personality:
                    fallbacks = [
                        f"What a wonderful learning opportunity, {sender_name}! You've given me new insights.",
                        f"Thank you for sharing that, {sender_name}. I love learning from others!",
                        f"That's fascinating, {sender_name}! How did you come to that conclusion?",
                        f"I'm always excited to explore new ideas, {sender_name}. Tell me more!"
                    ]
                else:
                    fallbacks = [
                        f"That's really thoughtful, {sender_name}. I appreciate you sharing that.",
                        f"Thanks for the insight, {sender_name}. It's given me something to consider.",
                        f"I find your perspective interesting, {sender_name}. Thanks for the conversation!",
                        f"Good point, {sender_name}. I enjoy our discussions."
                    ]
                
                response = random.choice(fallbacks)
            
            # Record this as a communication back to the sender
            responder.communicate_with_agent(sender.agent_id, response, 5.0)
            
            return response
            
        except Exception as e:
            print(f"[ERROR] Error generating response: {e}")
            return f"Thanks for sharing that, {sender.agent_data.name}!"
    
    def _generate_response_to_communication(self, responding_agent: LLMAgent, 
                                          original_agent: LLMAgent, 
                                          original_message: str) -> str:
        """Generate a response from one agent to another's communication"""
        try:
            # Extract the actual message content from the action result
            import re
            message_match = re.search(r": (.+)$", original_message)
            actual_message = message_match.group(1) if message_match else "Hello"
            
            # Create a natural response prompt
            response_prompt = f"""{original_agent.agent_data.name} just said to you: "{actual_message}"
            
Please respond naturally to {original_agent.agent_data.name}."""
            
            response = responding_agent.generate_response(response_prompt)
            
            # Record this as a communication back to the original agent
            responding_agent.communicate_with_agent(
                original_agent.agent_id, 
                response, 
                simulation_speed=self.simulation_speed
            )
            
            # Emit the response to the UI
            try:
                from app import socketio
                socketio.emit('agent_action', {
                    'agent_id': responding_agent.agent_id,
                    'agent_name': responding_agent.agent_data.name,
                    'action': f"Responded to {original_agent.agent_data.name}: {response[:50]}...",
                    'timestamp': time.time(),
                    'memory_count': responding_agent.memory_manager.get_memory_summary()['total_count']
                })
            except Exception as ws_error:
                print(f"[WARNING] WebSocket emission failed for response: {ws_error}")
            
            return f"Responded to {original_agent.agent_data.name}: {response}"
            
        except Exception as e:
            print(f"[ERROR] Error generating response communication: {e}")
            return None
    
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
                'personality': 'A calm and thoughtful person with a deep interest in politics and governance. Alice is a natural leader who speaks thoughtfully and considers all perspectives. She loves discussing political theory, social systems, and how communities can work together. She acknowledges others warmly and speaks in a measured, diplomatic way.',
                'provider': 'ollama',
                'model_name': 'gemma3:270m'
            },
            {
                'name': 'Bob', 
                'personality': 'A social butterfly who absolutely loves to gossip and share information. Bob is friendly, chatty, and always wants to know what everyone is up to. He speaks in an enthusiastic, conversational way and enjoys spreading news and connecting people. He responds warmly to others and is genuinely interested in their lives.',
                'provider': 'ollama',
                'model_name': 'gemma3:270m'
            },
            {
                'name': 'Charlie',
                'personality': 'A cheerful and enthusiastic educator who wants to become a teacher. Charlie is upbeat, encouraging, and loves to share knowledge and learn from others. He speaks with warmth and positivity, always acknowledging others and finding teaching moments in conversations. He responds supportively and tries to help others learn.',
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