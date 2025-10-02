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
                if "gossip" in self.agent_data.personality.lower():
                    response = "I wonder what everyone's been up to lately..."
                elif "politics" in self.agent_data.personality.lower() or "calm" in self.agent_data.personality.lower():
                    response = "I'm thinking about how we could better organize ourselves."
                elif "teacher" in self.agent_data.personality.lower() or "happy" in self.agent_data.personality.lower():
                    response = "There's so much to learn and share with others!"
                else:
                    response = "I'm observing and considering what to do next."
            
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
    
    def _build_prompt(self, prompt: str, context: str = "") -> str:
        """Build a complete prompt with personality and memory context"""
        # Get conversation context for better awareness
        conversation_context = self.memory_manager.get_conversation_context(limit=3)
        
        # Get recent meaningful actions (not just observations)
        recent_memories = self.memory_manager.get_memories(limit=5)
        action_memories = [m for m in recent_memories if "performed action:" in m.content and "observe" not in m.content.lower()]
        recent_actions = "\n".join([f"- {m.content}" for m in action_memories[:2]]) if action_memories else ""
        
        # Build a much simpler, more direct prompt
        if "What would you like to do" in prompt or "choose" in prompt.lower():
            # Decision-making prompt - keep it simple
            full_prompt = f"""You are {self.agent_data.name}. {self.agent_data.personality}

Choose ONE action:
COMMUNICATE, OBSERVE, CREATE_GOVERNMENT, or FORM_SOCIETY

Your choice:"""
        else:
            # Regular response prompt - be natural  
            full_prompt = f"""{self.agent_data.name}: {self.agent_data.personality}

{prompt}

Respond as {self.agent_data.name} in 1-2 sentences:"""
        
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
                   target_agent_id: int = None, metadata: Dict[str, Any] = None) -> bool:
        """Attempt to take an action in the environment"""
        if not self.is_active():
            return False
        
        # Check if agent can act according to environment rules
        if not self.environment_manager.can_agent_act(self.agent_id):
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
    
    def communicate_with_agent(self, target_agent_id: int, message: str) -> str:
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
            metadata={'message': message, 'target_name': target_name}
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
        
        if "gossip" in personality_lower:
            if avoid_repetition and "interesting" in conversation_history:
                return f"Hey {target_agent.name}, I noticed you've been active! Any new developments?"
            else:
                return f"Hey {target_agent.name}, have you heard anything interesting lately?"
        
        elif "politics" in personality_lower or "calm" in personality_lower:
            if avoid_repetition and "leadership" in conversation_history:
                return f"Hi {target_agent.name}, what do you think about the current state of our community?"
            else:
                return f"Hi {target_agent.name}, I've been thinking about leadership and society. Your thoughts?"
        
        elif "teacher" in personality_lower or "happy" in personality_lower:
            if avoid_repetition and "learn" in conversation_history:
                return f"Hello {target_agent.name}! How are you applying what you've learned recently?"
            else:
                return f"Hello {target_agent.name}! What have you discovered or learned lately?"
        
        else:
            # Generic friendly messages with variation
            varied_greetings = [
                f"Hey {target_agent.name}, how are things going?",
                f"Hi {target_agent.name}, what's on your mind?",
                f"{target_agent.name}, want to chat about what's happening?",
                f"Hello {target_agent.name}, how has your day been?",
                f"{target_agent.name}, I'd love to hear your perspective on things!"
            ]
            return random.choice(varied_greetings)
    
    def form_society(self, society_name: str, description: str) -> bool:
        """Attempt to form a new society"""
        return self.take_action(
            "form_society",
            f"Formed society: {society_name} - {description}",
            metadata={
                'society_name': society_name,
                'description': description
            }
        )
    
    def create_government(self, gov_name: str, gov_type: str, policies: List[str] = None) -> bool:
        """Attempt to create a government"""
        return self.take_action(
            "create_government",
            f"Created government: {gov_name} ({gov_type})",
            metadata={
                'government_name': gov_name,
                'government_type': gov_type,
                'policies': policies or []
            }
        )
    
    def influence_environment(self, influence_type: str, change_amount: float = 0.1) -> bool:
        """Attempt to influence the environment"""
        return self.take_action(
            "influence",
            f"Influenced environment: {influence_type}",
            metadata={
                'influence_type': influence_type,
                'influence_change': change_amount
            }
        )
    
    def autonomous_action(self) -> Optional[str]:
        """Perform an autonomous action based on current state and personality"""
        print(f"[DEBUG] {self.agent_data.name} attempting autonomous action...")
        print(f"[MEMORY] {self.agent_data.name} memory status: {self.memory_manager.get_memory_summary()}")
        
        if not self.is_active():
            print(f"[DEBUG] {self.agent_data.name} is not active, skipping autonomous action")
            return None
        
        try:
            # Get current environment state for context
            env_state = self.environment_manager.get_environment_state()
            print(f"[WORLD] Environment has {len(env_state.get('societies', []))} societies, {len(env_state.get('governments', []))} governments")
            
            print(f"[DEBUG] {self.agent_data.name} generating decision...")
            
            # Much simpler decision making - avoid context overload
            decision_prompt = f"""Choose ONE action word: COMMUNICATE, OBSERVE, CREATE_GOVERNMENT, or FORM_SOCIETY"""
            
            print(f"[DEBUG] {self.agent_data.name} calling generate_response...")
            decision = self.generate_response(decision_prompt, f"You are {self.agent_data.name}. {self.agent_data.personality}")
            print(f"[DECISION] {self.agent_data.name} decision: {decision}")
            
            # Parse and execute the decision with better keyword matching
            decision_upper = decision.upper().strip()
            
            # Force better decision parsing with personality bias
            if any(word in decision_upper for word in ["COMMUNICATE", "TALK", "CHAT", "SPEAK"]):
                action_choice = "COMMUNICATE"
            elif any(word in decision_upper for word in ["FORM_SOCIETY", "SOCIETY", "GROUP", "COMMUNITY"]):
                action_choice = "FORM_SOCIETY"
            elif any(word in decision_upper for word in ["CREATE_GOVERNMENT", "GOVERNMENT", "LEAD", "ORGANIZE"]):
                action_choice = "CREATE_GOVERNMENT"
            else:
                action_choice = "OBSERVE"  # Default fallback
            
            print(f"[ACTION] {self.agent_data.name} chose to {action_choice.lower()}")
            
            if action_choice == "COMMUNICATE":
                # Find another active agent to communicate with
                other_agents = Agent.query.filter(Agent.id != self.agent_id, Agent.is_active == True).all()
                if other_agents:
                    target = random.choice(other_agents)
                    print(f"[TARGET] {self.agent_data.name} selected {target.name} for communication")
                    
                    # Get conversation history with this specific agent to avoid repetition
                    conversation_history = self._get_conversation_history_with_agent(target.id)
                    print(f"[HISTORY] {self.agent_data.name} conversation history with {target.name}: {conversation_history[:100]}...")
                    
                    # Create varied conversation based on history and personality
                    message = self._generate_contextual_message(target, conversation_history)
                    
                    result = self.communicate_with_agent(target.id, message)
                    print(f"[COMM] Agent {self.agent_data.name} → {target.name}: {message}")
                    return f"Communicated with {target.name}: {message[:50]}..."
                else:
                    print(f"[DEBUG] No other agents available for communication")
                    return "No other agents available to communicate with"
            
            elif action_choice == "FORM_SOCIETY":
                society_name = f"{self.agent_data.name}'s Circle"
                self.form_society(society_name, f"A society formed by {self.agent_data.name} based on their values")
                print(f"[SOCIETY] Agent {self.agent_data.name}: Formed society: {society_name}")
                return f"Formed society: {society_name}"
            
            elif action_choice == "CREATE_GOVERNMENT":
                gov_name = f"{self.agent_data.name}'s Leadership"
                self.create_government(gov_name, "democracy", ["Fairness", "Progress"])
                print(f"[GOVERNMENT] Agent {self.agent_data.name}: Created government: {gov_name}")
                return f"Created government: {gov_name}"
            
            elif "INFLUENCE" in decision_upper:
                print(f"[ACTION] {self.agent_data.name} chose to influence environment")
                self.influence_environment("cultural_shift", 0.2)
                print(f"[INFLUENCE] Agent {self.agent_data.name}: Influenced the environment")
                return "Influenced the environment"
            
            # Default: observe (but make it more interesting)
            print(f"[ACTION] {self.agent_data.name} chose to observe")
            observation_prompts = [
                f"As {self.agent_data.name}, what do you notice happening around you right now?",
                f"You are {self.agent_data.name}. Make a brief observation about your current situation.",
                f"What catches {self.agent_data.name}'s attention in this moment?",
                f"As {self.agent_data.name}, describe something you're thinking about."
            ]
            observation_prompt = random.choice(observation_prompts)
            observation = self.generate_response(observation_prompt, f"You are {self.agent_data.name}. {self.agent_data.personality}. Respond naturally and briefly as yourself.")
            
            # Save observation action properly
            self.take_action("observe", f"Observed: {observation}", metadata={'observation': observation})
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