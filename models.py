from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()


class Character(db.Model):
    """Main character model - represents an evolving AI entity"""
    __tablename__ = 'characters'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    avatar = db.Column(db.String(20), default='🧑')  # Emoji avatar
    
    # Core personality (immutable foundation)
    core_personality = db.Column(db.Text, nullable=False)
    
    # LLM Configuration
    provider = db.Column(db.String(50), nullable=False)  # 'openai', 'gemini', 'ollama'
    model_name = db.Column(db.String(100), nullable=False)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    state = db.relationship('CharacterState', backref='character', uselist=False, cascade='all, delete-orphan')
    memories = db.relationship('Memory', backref='character', lazy=True, cascade='all, delete-orphan', foreign_keys='Memory.character_id')
    actions = db.relationship('Action', backref='character', lazy=True, cascade='all, delete-orphan', foreign_keys='Action.character_id')
    beliefs = db.relationship('Belief', backref='character', lazy=True, cascade='all, delete-orphan')
    evolutions = db.relationship('Evolution', backref='character', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self, include_state=False):
        data = {
            'id': self.id,
            'name': self.name,
            'avatar': self.avatar,
            'core_personality': self.core_personality,
            'provider': self.provider,
            'model_name': self.model_name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_active': self.last_active.isoformat() if self.last_active else None
        }
        if include_state and self.state:
            data['state'] = self.state.to_dict()
        return data


class CharacterState(db.Model):
    """Evolving state of a character"""
    __tablename__ = 'character_states'
    
    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=False, unique=True)
    
    # Personality traits (evolve over time, -100 to +100)
    trait_curiosity = db.Column(db.Integer, default=50)
    trait_empathy = db.Column(db.Integer, default=50)
    trait_assertiveness = db.Column(db.Integer, default=50)
    trait_creativity = db.Column(db.Integer, default=50)
    trait_trust = db.Column(db.Integer, default=50)
    trait_optimism = db.Column(db.Integer, default=50)
    
    # Current emotional state
    emotional_state = db.Column(db.String(50), default='neutral')  # happy, sad, curious, anxious, etc.
    energy_level = db.Column(db.Integer, default=100)  # 0-100
    
    # Conversation stats for evolution
    total_conversations = db.Column(db.Integer, default=0)
    conversations_since_evolution = db.Column(db.Integer, default=0)
    
    # JSON fields for complex data
    relationships_json = db.Column(db.Text, default='{}')  # {char_id: {"affinity": 0-100, "trust": 0-100, "history": []}}
    knowledge_json = db.Column(db.Text, default='[]')  # List of learned things
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def relationships(self):
        return json.loads(self.relationships_json) if self.relationships_json else {}
    
    @relationships.setter
    def relationships(self, value):
        self.relationships_json = json.dumps(value)
    
    @property
    def knowledge(self):
        return json.loads(self.knowledge_json) if self.knowledge_json else []
    
    @knowledge.setter
    def knowledge(self, value):
        self.knowledge_json = json.dumps(value)
    
    def to_dict(self):
        return {
            'character_id': self.character_id,
            'traits': {
                'curiosity': self.trait_curiosity,
                'empathy': self.trait_empathy,
                'assertiveness': self.trait_assertiveness,
                'creativity': self.trait_creativity,
                'trust': self.trait_trust,
                'optimism': self.trait_optimism
            },
            'emotional_state': self.emotional_state,
            'energy_level': self.energy_level,
            'total_conversations': self.total_conversations,
            'relationships': self.relationships,
            'knowledge': self.knowledge,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Belief(db.Model):
    """Beliefs formed through experience"""
    __tablename__ = 'beliefs'
    
    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)  # "Cooperation leads to better outcomes"
    reason = db.Column(db.Text)  # "Formed after successful collaboration with Bob"
    strength = db.Column(db.Integer, default=50)  # 0-100, how strongly held
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'reason': self.reason,
            'strength': self.strength,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Evolution(db.Model):
    """Record of character evolution events"""
    __tablename__ = 'evolutions'
    
    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=False)
    evolution_type = db.Column(db.String(50), nullable=False)  # 'trait_change', 'belief_formed', 'relationship_change'
    description = db.Column(db.Text, nullable=False)
    reasoning = db.Column(db.Text)  # LLM's self-reasoning for the change
    changes_json = db.Column(db.Text)  # {"trait_trust": +5, "belief": "..."}
    triggered_by = db.Column(db.Text)  # What conversation/event caused this
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def changes(self):
        return json.loads(self.changes_json) if self.changes_json else {}
    
    def to_dict(self):
        return {
            'id': self.id,
            'evolution_type': self.evolution_type,
            'description': self.description,
            'reasoning': self.reasoning,
            'changes': self.changes,
            'triggered_by': self.triggered_by,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Memory(db.Model):
    """Character memories"""
    __tablename__ = 'memories'
    
    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    memory_type = db.Column(db.String(50), nullable=False)  # 'short_term', 'long_term', 'core'
    importance_score = db.Column(db.Float, default=1.0)
    emotional_tag = db.Column(db.String(50))  # happy, sad, important, etc.
    related_character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'character_id': self.character_id,
            'content': self.content,
            'memory_type': self.memory_type,
            'importance_score': self.importance_score,
            'emotional_tag': self.emotional_tag,
            'related_character_id': self.related_character_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }


class Action(db.Model):
    """Actions performed by characters"""
    __tablename__ = 'actions'
    
    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=False)
    action_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    target_character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=True)
    success = db.Column(db.Boolean, default=True)
    action_metadata = db.Column(db.Text)  # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'character_id': self.character_id,
            'action_type': self.action_type,
            'description': self.description,
            'target_character_id': self.target_character_id,
            'success': self.success,
            'metadata': json.loads(self.action_metadata) if self.action_metadata else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class GodMessage(db.Model):
    """Messages from God (user) to characters"""
    __tablename__ = 'god_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    message_type = db.Column(db.String(50), nullable=False)  # 'broadcast', 'whisper'
    content = db.Column(db.Text, nullable=False)
    target_character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=True)  # Null for broadcast
    responses_json = db.Column(db.Text)  # JSON of character responses
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def responses(self):
        return json.loads(self.responses_json) if self.responses_json else []
    
    def to_dict(self):
        return {
            'id': self.id,
            'message_type': self.message_type,
            'content': self.content,
            'target_character_id': self.target_character_id,
            'responses': self.responses,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Simulation(db.Model):
    """Simulation state and settings"""
    __tablename__ = 'simulation'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), default='LLMverse')
    is_running = db.Column(db.Boolean, default=False)
    day = db.Column(db.Integer, default=1)
    speed = db.Column(db.Float, default=5.0)  # Seconds between actions
    settings_json = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def settings(self):
        return json.loads(self.settings_json) if self.settings_json else {}
    
    @settings.setter
    def settings(self, value):
        self.settings_json = json.dumps(value)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'is_running': self.is_running,
            'day': self.day,
            'speed': self.speed,
            'settings': self.settings,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# Keep Environment for backward compatibility but simplified
class Environment(db.Model):
    __tablename__ = 'environment'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)
    rules = db.Column(db.Text)
    state = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'rules': json.loads(self.rules) if self.rules else None,
            'state': json.loads(self.state) if self.state else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# Backward compatibility alias
Agent = Character