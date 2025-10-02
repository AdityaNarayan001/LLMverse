import json
from typing import Dict, Any, List
from datetime import datetime
from models import Environment, Action, Agent, db

class EnvironmentManager:
    """Manages the shared environment where agents interact"""
    
    def __init__(self):
        self.current_environment = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Ensure the manager is initialized with database access"""
        if not self._initialized:
            self.load_active_environment()
            self._initialized = True
    
    def load_active_environment(self):
        """Load the currently active environment"""
        self.current_environment = Environment.query.filter_by(is_active=True).first()
        if not self.current_environment:
            # Create default environment if none exists
            self.create_default_environment()
    
    def create_default_environment(self):
        """Create a default environment"""
        default_rules = {
            "communication": True,
            "action_cooldown": 5,  # seconds between actions
            "max_daily_actions": 100,
            "influence_decay": 0.1,
            "society_building": True,
            "governance_formation": True
        }
        
        default_state = {
            "societies": [],
            "governments": [],
            "relationships": {},
            "global_influence": {},
            "events": [],
            "day": 1
        }
        
        environment = Environment(
            name="Default Simulation",
            description="A basic simulation environment where agents can communicate, form societies, and create governments.",
            rules=json.dumps(default_rules),
            state=json.dumps(default_state),
            is_active=True
        )
        
        db.session.add(environment)
        db.session.commit()
        self.current_environment = environment
    
    def create_environment(self, name: str, description: str, rules: Dict[str, Any], 
                          initial_state: Dict[str, Any] = None) -> Environment:
        """Create a new environment"""
        if initial_state is None:
            initial_state = {
                "societies": [],
                "governments": [],
                "relationships": {},
                "global_influence": {},
                "events": [],
                "day": 1
            }
        
        environment = Environment(
            name=name,
            description=description,
            rules=json.dumps(rules),
            state=json.dumps(initial_state),
            is_active=False
        )
        
        db.session.add(environment)
        db.session.commit()
        return environment
    
    def switch_environment(self, environment_id: int) -> bool:
        """Switch to a different environment"""
        new_env = Environment.query.get(environment_id)
        if not new_env:
            return False
        
        # Deactivate current environment
        current_env = Environment.query.filter_by(is_active=True).first()
        if current_env:
            current_env.is_active = False
        
        # Activate new environment
        new_env.is_active = True
        new_env.updated_at = datetime.utcnow()
        
        db.session.commit()
        self.current_environment = new_env
        return True
    
    def get_environment_state(self) -> Dict[str, Any]:
        """Get the current environment state"""
        self._ensure_initialized()
        
        # Always fetch fresh from database to avoid DetachedInstanceError
        from models import Environment, db
        env = Environment.query.first()
        if not env:
            return {}
        
        return json.loads(env.state) if env.state else {}
    
    def update_environment_state(self, new_state: Dict[str, Any]):
        """Update the environment state"""
        # Always fetch fresh from database to avoid DetachedInstanceError
        env = Environment.query.filter_by(is_active=True).first()
        if not env:
            return
        
        env.state = json.dumps(new_state)
        env.updated_at = datetime.utcnow()
        db.session.commit()
    
    def get_environment_rules(self) -> Dict[str, Any]:
        """Get the current environment rules"""
        # Always fetch fresh from database to avoid DetachedInstanceError
        from models import Environment, db
        env = Environment.query.first()
        if not env:
            return {}
        
        return json.loads(env.rules) if env.rules else {}
    
    def can_agent_act(self, agent_id: int) -> bool:
        """Check if an agent can perform an action based on environment rules"""
        self._ensure_initialized()
        rules = self.get_environment_rules()
        
        # Check daily action limit
        max_daily_actions = rules.get('max_daily_actions', 100)
        today_actions = Action.query.filter(
            Action.agent_id == agent_id,
            Action.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count()
        
        if today_actions >= max_daily_actions:
            return False
        
        # Check cooldown
        action_cooldown = rules.get('action_cooldown', 5)
        last_action = Action.query.filter_by(agent_id=agent_id).order_by(Action.created_at.desc()).first()
        
        if last_action:
            time_since_last = (datetime.utcnow() - last_action.created_at).total_seconds()
            if time_since_last < action_cooldown:
                return False
        
        return True
    
    def record_action(self, agent_id: int, action_type: str, description: str, 
                     target_agent_id: int = None, metadata: Dict[str, Any] = None) -> Action:
        """Record an action performed by an agent"""
        self._ensure_initialized()
        action = Action(
            agent_id=agent_id,
            action_type=action_type,
            description=description,
            target_agent_id=target_agent_id,
            action_metadata=json.dumps(metadata) if metadata else None
        )
        
        db.session.add(action)
        db.session.commit()
        
        # Update environment state based on the action
        self._process_action_effects(action)
        
        return action
    
    def _process_action_effects(self, action: Action):
        """Process the effects of an action on the environment"""
        state = self.get_environment_state()
        rules = self.get_environment_rules()
        
        # Process different types of actions
        if action.action_type == "communicate":
            self._process_communication(action, state, rules)
        elif action.action_type == "form_society":
            self._process_society_formation(action, state, rules)
        elif action.action_type == "create_government":
            self._process_government_creation(action, state, rules)
        elif action.action_type == "influence":
            self._process_influence(action, state, rules)
        
        # Update the environment state
        self.update_environment_state(state)
    
    def _process_communication(self, action: Action, state: Dict[str, Any], rules: Dict[str, Any]):
        """Process communication effects"""
        if not rules.get('communication', True):
            return
        
        # Update relationships
        if action.target_agent_id:
            relationships = state.get('relationships', {})
            agent_key = f"{action.agent_id}_{action.target_agent_id}"
            relationships[agent_key] = relationships.get(agent_key, 0) + 1
            state['relationships'] = relationships
    
    def _process_society_formation(self, action: Action, state: Dict[str, Any], rules: Dict[str, Any]):
        """Process society formation"""
        if not rules.get('society_building', True):
            return
        
        societies = state.get('societies', [])
        metadata = json.loads(action.action_metadata) if action.action_metadata else {}
        
        society = {
            'id': len(societies) + 1,
            'name': metadata.get('society_name', f"Society {len(societies) + 1}"),
            'founder': action.agent_id,
            'members': [action.agent_id],
            'created_at': action.created_at.isoformat(),
            'influence': 1.0
        }
        
        societies.append(society)
        state['societies'] = societies
    
    def _process_government_creation(self, action: Action, state: Dict[str, Any], rules: Dict[str, Any]):
        """Process government creation"""
        if not rules.get('governance_formation', True):
            return
        
        governments = state.get('governments', [])
        metadata = json.loads(action.action_metadata) if action.action_metadata else {}
        
        government = {
            'id': len(governments) + 1,
            'name': metadata.get('government_name', f"Government {len(governments) + 1}"),
            'leader': action.agent_id,
            'type': metadata.get('government_type', 'democracy'),
            'created_at': action.created_at.isoformat(),
            'influence': 1.0,
            'policies': []
        }
        
        governments.append(government)
        state['governments'] = governments
    
    def _process_influence(self, action: Action, state: Dict[str, Any], rules: Dict[str, Any]):
        """Process influence changes"""
        global_influence = state.get('global_influence', {})
        agent_id_str = str(action.agent_id)
        
        metadata = json.loads(action.action_metadata) if action.action_metadata else {}
        influence_change = metadata.get('influence_change', 0.1)
        
        global_influence[agent_id_str] = global_influence.get(agent_id_str, 0) + influence_change
        state['global_influence'] = global_influence
    
    def get_recent_actions(self, limit: int = 50) -> List[Action]:
        """Get recent actions in the environment"""
        return Action.query.order_by(Action.created_at.desc()).limit(limit).all()
    
    def reset_environment(self):
        """Reset the current environment to its initial state"""
        # Always fetch fresh from database to avoid DetachedInstanceError
        env = Environment.query.filter_by(is_active=True).first()
        if not env:
            return
        
        # Clear all actions
        Action.query.delete()
        
        # Reset environment state
        initial_state = {
            "societies": [],
            "governments": [],
            "relationships": {},
            "global_influence": {},
            "events": [],
            "day": 1
        }
        
        env.state = json.dumps(initial_state)
        env.updated_at = datetime.utcnow()
        
        db.session.commit()
    
    def get_all_environments(self) -> List[Environment]:
        """Get all available environments"""
        return Environment.query.all()