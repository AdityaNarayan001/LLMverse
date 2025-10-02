from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Agent(db.Model):
    __tablename__ = 'agents'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    personality = db.Column(db.Text, nullable=False)
    provider = db.Column(db.String(50), nullable=False)  # 'openai', 'gemini', 'ollama'
    model_name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    memories = db.relationship('Memory', backref='agent', lazy=True, cascade='all, delete-orphan')
    actions = db.relationship('Action', backref='agent', lazy=True, cascade='all, delete-orphan', foreign_keys='Action.agent_id')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'personality': self.personality,
            'provider': self.provider,
            'model_name': self.model_name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_active': self.last_active.isoformat() if self.last_active else None
        }

class Memory(db.Model):
    __tablename__ = 'memories'
    
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    memory_type = db.Column(db.String(50), nullable=False)  # 'short_term', 'long_term'
    importance_score = db.Column(db.Float, default=1.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'content': self.content,
            'memory_type': self.memory_type,
            'importance_score': self.importance_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }

class Action(db.Model):
    __tablename__ = 'actions'
    
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False)
    action_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    target_agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=True)
    success = db.Column(db.Boolean, default=True)
    action_metadata = db.Column(db.Text)  # JSON string for additional data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'action_type': self.action_type,
            'description': self.description,
            'target_agent_id': self.target_agent_id,
            'success': self.success,
            'metadata': json.loads(self.action_metadata) if self.action_metadata else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Environment(db.Model):
    __tablename__ = 'environment'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)
    rules = db.Column(db.Text)  # JSON string for environment rules
    state = db.Column(db.Text)  # JSON string for current state
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