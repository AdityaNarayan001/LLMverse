import random
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from models import Agent, db
from src.providers.factory import ProviderFactory
from src.memory import MemoryManager
from src.environment import EnvironmentManager

class LLMAgent:
    """Represents an LLM agent with personality, memory, and behavior"""
    
    def __init__(self, agent_id: int, environment_manager: EnvironmentManager):
        print(f"[DEBUG] Initializing LLMAgent with ID: {agent_id}")
        self.agent_id = agent_id
        self.environment_manager = environment_manager
        self.memory_manager = MemoryManager(agent_id)
        self.provider = None
        self.agent_data = None
        
        try:
            self.load_agent_data()
            print(f"[DEBUG] Agent data loaded for: {self.agent_data.name}")
        except Exception as e:
            print(f"[ERROR] Failed to load agent data: {e}")
            raise
        
        try:
            self.setup_provider()
            print(f"[DEBUG] Provider setup for {self.agent_data.name}: {self.provider is not None}")
        except Exception as e:
            print(f"[ERROR] Failed to setup provider: {e}")
            raise
    
    def load_agent_data(self):
        """Load agent data from database"""
        self.agent_data = Agent.query.get(self.agent_id)
        if not self.agent_data:
            raise ValueError(f"Agent with ID {self.agent_id} not found")
    
    def setup_provider(self):
        """Setup the LLM provider for this agent"""
        if not self.agent_data:
            return
        
        try:
            provider_config = self._get_provider_config()
            self.provider = ProviderFactory.create_provider(
                self.agent_data.provider,
                **provider_config
            )
        except Exception as e:
            print(f"Failed to setup provider for agent {self.agent_id}: {e}")
            self.provider = None
    
    def _get_provider_config(self) -> Dict[str, Any]:
        """Get provider configuration from environment/config"""
        from config import Config
        
        if self.agent_data.provider == 'openai':
            return {'api_key': Config.OPENAI_API_KEY}
        elif self.agent_data.provider == 'gemini':
            return {'api_key': Config.GEMINI_API_KEY}
        elif self.agent_data.provider == 'ollama':
            return {'base_url': Config.OLLAMA_BASE_URL}
        
        return {}
    
    def is_active(self) -> bool:
        """Check if the agent is active and can operate"""
        print(f"[DEBUG] Checking if agent {self.agent_data.name if self.agent_data else 'Unknown'} is active...")
        
        if not self.agent_data:
            print(f"[DEBUG] Agent data is None")
            return False
        
        if not self.agent_data.is_active:
            print(f"[DEBUG] Agent {self.agent_data.name} is not active in database")
            return False
        
        if not self.provider:
            print(f"[DEBUG] Agent {self.agent_data.name} has no provider")
            return False
        
        try:
            provider_available = self.provider.is_available()
            print(f"[DEBUG] Provider availability for {self.agent_data.name}: {provider_available}")
            
            result = (self.agent_data and 
                     self.agent_data.is_active and 
                     self.provider and 
                     provider_available)
            
            print(f"[DEBUG] Final active status for {self.agent_data.name}: {result}")
            return result
        except Exception as e:
            print(f"[ERROR] Error checking provider availability: {e}")
            return False
    
    def generate_response(self, prompt: str, context: str = "") -> str:
        """Generate a response using the agent's LLM provider"""
        print(f"[DEBUG] {self.agent_data.name} generating response to: {prompt[:50]}...")
        
        if not self.is_active():
            print(f"[DEBUG] {self.agent_data.name} is not active, cannot generate response")
            return "Agent is not available"
        
        # Check if this is a relevant conversational prompt for an AI agent
        if self._is_irrelevant_prompt(prompt):
            return self._get_relevance_redirect_response(prompt)
        
        # Build the full prompt with personality and context
        full_prompt = self._build_prompt(prompt, context)
        print(f"[DEBUG] {self.agent_data.name} built prompt, length: {len(full_prompt)}")
        
        try:
            print(f"[DEBUG] {self.agent_data.name} calling provider.generate_response...")
            response = self.provider.generate_response(
                full_prompt, 
                model=self.agent_data.model_name
            )
            print(f"[DEBUG] {self.agent_data.name} got response: {response[:100]}...")
            
            # Clean up generic responses that small models tend to give
            if (response.startswith("Okay, I understand") or 
                response.startswith("I understand") or
                "I will respond" in response or
                "I will follow" in response):
                
                print(f"[DEBUG] {self.agent_data.name} gave generic response, generating fallback...")
                # Generate a personality-based fallback response
                if "gossip" in self.agent_data.personality.lower() or "social" in self.agent_data.personality.lower():
                    responses = [
                        "Oh, I'm always curious about what everyone's been up to!",
                        "I love hearing about what's happening around here!",
                        "There's always something interesting going on, don't you think?"
                    ]
                    response = random.choice(responses)
                elif "politics" in self.agent_data.personality.lower() or "governance" in self.agent_data.personality.lower():
                    responses = [
                        "I've been thinking about how we could work together more effectively.",
                        "There's always room for better organization and cooperation.",
                        "I believe we can build something great if we work together thoughtfully."
                    ]
                    response = random.choice(responses)
                elif "teacher" in self.agent_data.personality.lower() or "education" in self.agent_data.personality.lower():
                    responses = [
                        "I'm always excited to learn something new or share what I know!",
                        "There's so much we can teach each other if we stay curious!",
                        "Every conversation is a chance to learn and grow together!"
                    ]
                    response = random.choice(responses)
                else:
                    responses = [
                        "I'm observing and thinking about what to do next.",
                        "It's interesting to see how things develop around here.",
                        "I'm taking things in and considering my next move."
                    ]
                    response = random.choice(responses)
            
            # Store the interaction in memory
            self.memory_manager.add_memory(
                f"User said: {prompt}\nI responded: {response}",
                memory_type='short_term',
                importance_score=2.0
            )
            
            return response
        except Exception as e:
            print(f"[ERROR] Error generating response for {self.agent_data.name}: {e}")
            import traceback
            traceback.print_exc()
            return f"Error generating response: {str(e)}"
    
    def _is_irrelevant_prompt(self, prompt: str) -> bool:
        """Check if the prompt is irrelevant to the agent's purpose"""
        prompt_lower = prompt.lower().strip()
        
        # Math questions
        if any(op in prompt_lower for op in ['+', '-', '*', '/', '=', 'what is', 'calculate', 'solve']):
            # Check for simple math patterns
            import re
            if re.search(r'\b\d+\s*[+\-*/]\s*\d+\b', prompt_lower):
                return True
        
        # Programming/code questions
        if any(term in prompt_lower for term in ['function', 'variable', 'loop', 'array', 'python', 'javascript', 'code', 'programming', 'algorithm']):
            return True
        
        # Technical/factual questions that aren't conversational
        if any(term in prompt_lower for term in ['what year', 'when was', 'who invented', 'capital of', 'population of', 'definition of']):
            return True
        
        # Random/test inputs
        if len(prompt.strip()) < 3 or prompt_lower in ['test', 'hello', 'hi', '?', '.', '!']:
            return True
            
        return False
    
    def _get_relevance_redirect_response(self, prompt: str) -> str:
        """Get a response that redirects to the agent's purpose"""
        prompt_lower = prompt.lower()
        
        # Math-specific response
        if any(op in prompt_lower for op in ['+', '-', '*', '/', '=']) or 'what is' in prompt_lower:
            return f"I'm {self.agent_data.name}, an AI agent focused on social interaction and community building. For math calculations, you might want to use a calculator or ask a different AI assistant!"
        
        # Generic redirect based on personality
        if "gossip" in self.agent_data.personality.lower() or "social" in self.agent_data.personality.lower():
            return f"Hi! I'm {self.agent_data.name} and I love chatting about social topics, relationships, and what's happening in our community. What would you like to talk about?"
        elif "politics" in self.agent_data.personality.lower() or "governance" in self.agent_data.personality.lower():
            return f"Hello! I'm {self.agent_data.name} and I'm interested in discussing governance, leadership, and how we can work together as a community. What are your thoughts on these topics?"
        elif "teacher" in self.agent_data.personality.lower() or "education" in self.agent_data.personality.lower():
            return f"Hi there! I'm {self.agent_data.name} and I love discussing learning, education, and sharing knowledge. What would you like to explore together?"
        else:
            return f"Hello! I'm {self.agent_data.name}. I'm designed for meaningful conversations about social interaction, community building, and related topics. What would you like to discuss?"
    
    def _build_prompt(self, prompt: str, context: str = "") -> str:
        """Build a complete prompt with personality and memory context"""
        # Get conversation context for better awareness
        conversation_context = self.memory_manager.get_conversation_context(limit=3)
        
        # Get recent meaningful actions (not just observations)
        recent_memories = self.memory_manager.get_memories(limit=5)
        action_memories = [m for m in recent_memories if "performed action:" in m.content and "observe" not in m.content.lower()]
        recent_actions = "\n".join([f"- {m.content}" for m in action_memories[:2]]) if action_memories else ""
        
        # Build a much simpler, more direct prompt for natural conversation
        if "What would you like to do" in prompt or "choose" in prompt.lower():
            # Decision-making prompt - keep it simple
            full_prompt = f"""You are {self.agent_data.name}. {self.agent_data.personality}

Choose ONE action:
COMMUNICATE, OBSERVE, CREATE_GOVERNMENT, or FORM_SOCIETY

Your choice:"""
        elif "just said to you:" in prompt:
            # This is a response to another agent - be natural and conversational
            full_prompt = f"""You are {self.agent_data.name}. {self.agent_data.personality}

{prompt}

Respond naturally as {self.agent_data.name} would. Acknowledge what they said and respond in a friendly, conversational way:"""
        else:
            # Regular response prompt - be natural  
            full_prompt = f"""{self.agent_data.name}: {self.agent_data.personality}

{prompt}

Respond as {self.agent_data.name} in 1-2 sentences. Be natural and conversational:"""
        
        return full_prompt
    
    def _get_world_context(self) -> str:
        """Get context about what's happening in the world with other agents"""
        from models import Agent
        
        # Get info about other agents
        other_agents = Agent.query.filter(Agent.id != self.agent_id).all()
        agent_info = []
        
        for agent in other_agents:
            agent_info.append(f"- {agent.name}: {agent.personality}")
        
        # Get recent environment state
        env_state = self.environment_manager.get_environment_state()
        societies = env_state.get('societies', [])
        governments = env_state.get('governments', [])
        
        world_info = []
        world_info.append("Other agents in this world:")
        world_info.extend(agent_info[:3])  # Limit to avoid overload
        
        if societies:
            world_info.append(f"Societies formed: {len(societies)} society/societies exist")
        if governments:
            world_info.append(f"Governments created: {len(governments)} government(s) exist")
        
        return "\n".join(world_info)
    
    def take_action(self, action_type: str, description: str, 
                   target_agent_id: int = None, metadata: Dict[str, Any] = None, 
                   simulation_speed: float = 5.0) -> bool:
        """Attempt to take an action in the environment"""
        if not self.is_active():
            return False
        
        # Check if agent can act according to environment rules
        if not self.environment_manager.can_agent_act(self.agent_id, simulation_speed):
            return False
        
        # Record the action
        action = self.environment_manager.record_action(
            self.agent_id, action_type, description, target_agent_id, metadata
        )
        
        # Update agent's last active time
        self.agent_data.last_active = datetime.utcnow()
        db.session.commit()
        
        # Store action in memory
        self.memory_manager.add_memory(
            f"I performed action: {action_type} - {description}",
            memory_type='short_term',
            importance_score=3.0
        )
        
        return True
    
    def communicate_with_agent(self, target_agent_id: int, message: str, simulation_speed: float = 5.0) -> str:
        """Communicate with another agent"""
        if not self.is_active():
            return "Cannot communicate - agent is not active"
        
        # Get target agent name for better memory storage
        from models import Agent
        target_agent = Agent.query.get(target_agent_id)
        target_name = target_agent.name if target_agent else f"Agent {target_agent_id}"
        
        # Record communication action with enhanced details
        self.take_action(
            "communicate",
            f"Sent message to {target_name}: {message}",
            target_agent_id=target_agent_id,
            metadata={'message': message, 'target_name': target_name},
            simulation_speed=simulation_speed
        )
        
        # Store in memory with higher importance for meaningful conversations
        importance = 4.0 if len(message.split()) > 5 else 2.0  # Longer messages are more important
        self.memory_manager.add_memory(
            f"I said to {target_name}: {message}",
            memory_type='short_term',
            importance_score=importance
        )
        
        print(f"[MEMORY] {self.agent_data.name} stored communication with {target_name} (importance: {importance})")
        
        # Just return the message - no need for additional processing
        return message
    
    def _get_conversation_history_with_agent(self, target_agent_id: int) -> str:
        """Get recent conversation history with a specific agent"""
        recent_convos = self.memory_manager.get_memories(limit=20)
        conversations_with_target = [
            m for m in recent_convos 
            if f"agent {target_agent_id}" in m.content or f"to agent {target_agent_id}" in m.content
        ]
        
        if not conversations_with_target:
            return "No previous conversations"
        
        return f"Last {len(conversations_with_target)} messages with this agent: " + "; ".join([
            m.content[:40] + "..." for m in conversations_with_target[:3]
        ])
    
    def _generate_contextual_message(self, target_agent, conversation_history: str) -> str:
        """Generate a contextual message based on personality and history"""
        # Avoid repetition by checking what was said before
        avoid_repetition = "No recent conversations" not in conversation_history
        
        personality_lower = self.agent_data.personality.lower()
        
        if "gossip" in personality_lower or "social" in personality_lower:
            messages = [
                f"Hey {target_agent.name}! I've been wondering what you've been up to lately?",
                f"Hi {target_agent.name}! Any interesting news or stories you want to share?",
                f"{target_agent.name}, I love chatting with you! What's the latest?",
                f"Oh {target_agent.name}! I'm so curious about what's happening with everyone.",
                f"Hey there {target_agent.name}! I heard some interesting things going around..."
            ]
            return messages[hash(conversation_history) % len(messages)] if avoid_repetition else messages[0]
        
        elif "politics" in personality_lower or "governance" in personality_lower or "leader" in personality_lower:
            messages = [
                f"Hello {target_agent.name}, I've been thinking about how we could better organize our community.",
                f"Hi {target_agent.name}, what are your thoughts on leadership and cooperation?",
                f"{target_agent.name}, I'd value your perspective on some governance ideas I've been considering.",
                f"Good to see you {target_agent.name}. I believe we could work together on some community initiatives.",
                f"Hello {target_agent.name}, I've been reflecting on what makes societies work well together."
            ]
            return messages[hash(conversation_history) % len(messages)] if avoid_repetition else messages[0]
        
        elif "teacher" in personality_lower or "education" in personality_lower or "learn" in personality_lower:
            messages = [
                f"Hello {target_agent.name}! I'm always excited to learn from others. What have you discovered lately?",
                f"Hi {target_agent.name}! I'd love to hear about something you're passionate about.",
                f"{target_agent.name}, I find our conversations so enriching! What's on your mind?",
                f"Hey {target_agent.name}! I believe we can all learn from each other. What's your perspective?",
                f"Hello {target_agent.name}! I'm curious about your thoughts and experiences."
            ]
            return messages[hash(conversation_history) % len(messages)] if avoid_repetition else messages[0]
        
        else:
            # Generic friendly messages with variation
            varied_greetings = [
                f"Hey {target_agent.name}, how are you doing today?",
                f"Hi {target_agent.name}, it's great to connect with you!",
                f"{target_agent.name}, I hope you're having a good time!",
                f"Hello {target_agent.name}, what's been on your mind lately?",
                f"{target_agent.name}, I always enjoy our conversations!",
                f"Hey there {target_agent.name}! What's new with you?",
                f"Hi {target_agent.name}, I'd love to hear your thoughts on things."
            ]
            return varied_greetings[hash(conversation_history) % len(varied_greetings)]
    
    def _generate_topical_message(self, target_agent, conversation_history: str) -> str:
        """Generate a topical message that builds on conversation themes"""
        personality_lower = self.agent_data.personality.lower()
        target_personality_lower = target_agent.personality.lower()
        
        # Create topic-focused conversations based on personality combinations
        if "gossip" in personality_lower or "social" in personality_lower:
            if "politics" in target_personality_lower:
                topics = [
                    f"Hi {target_agent.name}! I heard you're interested in politics - what do you think about how our community is organized?",
                    f"Hey {target_agent.name}, I'd love to hear your political insights! What changes would you make around here?",
                    f"{target_agent.name}, tell me about your ideas for leadership - I'm always curious about what people think!"
                ]
            elif "teacher" in target_personality_lower or "education" in target_personality_lower:
                topics = [
                    f"Hi {target_agent.name}! As an educator, what do you think people should know about getting along better?",
                    f"Hey {target_agent.name}, I love learning from teachers - what's the most important thing you'd want to share?",
                    f"{target_agent.name}, I'm curious about your teaching philosophy - what motivates you?"
                ]
            else:
                topics = [
                    f"Hey {target_agent.name}! What's the most interesting thing that's happened to you recently?",
                    f"Hi {target_agent.name}, I love hearing different perspectives - what's your take on how things are going?",
                    f"{target_agent.name}, tell me something about yourself that might surprise me!"
                ]
        
        elif "politics" in personality_lower or "governance" in personality_lower:
            if "teacher" in target_personality_lower:
                topics = [
                    f"Hello {target_agent.name}, I think education and governance go hand in hand. How do you see them connecting?",
                    f"Hi {target_agent.name}, as an educator, what do you think makes for good leadership in a community?",
                    f"{target_agent.name}, I believe we could collaborate on civic education - what are your thoughts?"
                ]
            elif "gossip" in target_personality_lower or "social" in target_personality_lower:
                topics = [
                    f"Hi {target_agent.name}, you always know what's happening - what do people think about our current situation?",
                    f"Hello {target_agent.name}, I value your social insights for understanding community needs. What are you hearing?",
                    f"{target_agent.name}, your social connections are valuable - how do you think we can better serve everyone?"
                ]
            else:
                topics = [
                    f"Hello {target_agent.name}, I'm thinking about community organization. What's your perspective on cooperation?",
                    f"Hi {target_agent.name}, I believe in collaborative governance. How do you think we should make decisions together?",
                    f"{target_agent.name}, what are your thoughts on creating systems that work for everyone?"
                ]
        
        elif "teacher" in personality_lower or "education" in personality_lower:
            if "politics" in target_personality_lower:
                topics = [
                    f"Hello {target_agent.name}, I think education shapes good citizenship. What qualities make a good leader?",
                    f"Hi {target_agent.name}, as someone interested in governance, what do you think people need to learn about community life?",
                    f"{target_agent.name}, I believe knowledge and leadership go together - what's your philosophy on this?"
                ]
            elif "gossip" in target_personality_lower or "social" in target_personality_lower:
                topics = [
                    f"Hi {target_agent.name}, you understand social dynamics so well! What have you observed about how people learn from each other?",
                    f"Hello {target_agent.name}, I think social connections are key to learning. What's your take on peer education?",
                    f"{target_agent.name}, your social insights could help me understand different learning styles - what do you think?"
                ]
            else:
                topics = [
                    f"Hello {target_agent.name}, I'm always curious about different perspectives on learning and growth. What's yours?",
                    f"Hi {target_agent.name}, I believe everyone has something valuable to teach. What would you like to share?",
                    f"{target_agent.name}, I'm interested in how we can all support each other's development - any thoughts?"
                ]
        
        else:
            # Default topical conversations
            topics = [
                f"Hi {target_agent.name}, I've been thinking about how we all fit together in this community. What's your view?",
                f"Hello {target_agent.name}, what do you think makes for meaningful interactions between people like us?",
                f"{target_agent.name}, I'm curious about your perspective on building better relationships - any insights?"
            ]
        
        # Choose a topic based on conversation history to avoid repetition
        return topics[hash(conversation_history + target_agent.name) % len(topics)]
    
    def form_society(self, society_name: str, description: str, simulation_speed: float = 5.0) -> bool:
        """Attempt to form a new society"""
        return self.take_action(
            "form_society",
            f"Formed society: {society_name} - {description}",
            metadata={
                'society_name': society_name,
                'description': description
            },
            simulation_speed=simulation_speed
        )
    
    def create_government(self, gov_name: str, gov_type: str, policies: List[str] = None, simulation_speed: float = 5.0) -> bool:
        """Attempt to create a government"""
        return self.take_action(
            "create_government",
            f"Created government: {gov_name} ({gov_type})",
            metadata={
                'government_name': gov_name,
                'government_type': gov_type,
                'policies': policies or []
            },
            simulation_speed=simulation_speed
        )
    
    def influence_environment(self, influence_type: str, change_amount: float = 0.1, simulation_speed: float = 5.0) -> bool:
        """Attempt to influence the environment"""
        return self.take_action(
            "influence",
            f"Influenced environment: {influence_type}",
            metadata={
                'influence_type': influence_type,
                'influence_change': change_amount
            },
            simulation_speed=simulation_speed
        )
    
    def autonomous_action(self, simulation_speed: float = 5.0) -> Optional[str]:
        """Perform an autonomous action based on current state and personality - simplified for round-robin"""
        print(f"[DEBUG] {self.agent_data.name} attempting autonomous action (round-robin mode)...")
        
        if not self.is_active():
            print(f"[DEBUG] {self.agent_data.name} is not active, skipping autonomous action")
            return None
        
        try:
            # In round-robin mode, agents primarily observe or take non-communication actions
            # Communication is handled by the agent manager
            
            personality_lower = self.agent_data.personality.lower()
            
            # Occasionally take special actions based on personality
            if random.random() < 0.3:  # 30% chance for special actions
                if "politics" in personality_lower and random.random() < 0.5:
                    # Politicians might create governments
                    gov_name = f"{self.agent_data.name}'s Initiative"
                    self.create_government(gov_name, "collaborative", ["Transparency", "Cooperation"], simulation_speed)
                    return f"Created government initiative: {gov_name}"
                
                elif "teacher" in personality_lower and random.random() < 0.5:
                    # Teachers might form educational societies
                    society_name = f"{self.agent_data.name}'s Learning Circle"
                    self.form_society(society_name, f"An educational community focused on learning and growth", simulation_speed)
                    return f"Formed learning society: {society_name}"
            
            # Most of the time, just observe with personality-driven observations
            observation_prompts = [
                f"As {self.agent_data.name}, what specific thing catches your attention right now?",
                f"You are {self.agent_data.name}. Make a brief, focused observation.",
                f"What is {self.agent_data.name} thinking about based on your personality?",
                f"As {self.agent_data.name}, what interests you most about the current situation?"
            ]
            
            observation_prompt = random.choice(observation_prompts)
            observation = self.generate_response(observation_prompt, f"Keep it brief and specific to your personality as {self.agent_data.name}.")
            
            # Save observation action
            self.take_action("observe", f"Observed: {observation}", metadata={'observation': observation}, simulation_speed=simulation_speed)
            print(f"[OBSERVE] Agent {self.agent_data.name}: {observation[:100]}...")
            return f"Observed: {observation[:100]}..."
            
        except Exception as e:
            print(f"[ERROR] Error in autonomous action for {self.agent_data.name}: {e}")
            import traceback
            traceback.print_exc()
            return f"Error: {str(e)}"
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the agent"""
        memory_summary = self.memory_manager.get_memory_summary()
        
        return {
            'id': self.agent_id,
            'name': self.agent_data.name,
            'personality': self.agent_data.personality,
            'provider': self.agent_data.provider,
            'model': self.agent_data.model_name,
            'is_active': self.is_active(),
            'last_active': self.agent_data.last_active.isoformat() if self.agent_data.last_active else None,
            'memory_summary': memory_summary,
            'provider_available': self.provider.is_available() if self.provider else False
        }