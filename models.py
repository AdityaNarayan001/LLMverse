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


# ─── Forum System ────────────────────────────────────────

class ForumTopic(db.Model):
    __tablename__ = 'forum_topics'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), default='general')
    started_by_agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=True)
    started_by_user = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    posts = db.relationship('ForumPost', backref='topic', lazy=True,
                           cascade='all, delete-orphan', order_by='ForumPost.created_at')
    starter_agent = db.relationship('Agent', backref='started_topics',
                                   foreign_keys=[started_by_agent_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'category': self.category,
            'started_by_agent_id': self.started_by_agent_id,
            'started_by_user': self.started_by_user,
            'starter_name': (self.starter_agent.name if self.starter_agent
                            else (self.started_by_user or 'Unknown')),
            'is_active': self.is_active,
            'is_pinned': self.is_pinned,
            'post_count': len(self.posts),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_activity_at': self.last_activity_at.isoformat() if self.last_activity_at else None,
        }


class ForumPost(db.Model):
    __tablename__ = 'forum_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('forum_topics.id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=True)
    user_name = db.Column(db.String(100), nullable=True)
    content = db.Column(db.Text, nullable=False)
    reply_to_id = db.Column(db.Integer, db.ForeignKey('forum_posts.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    author_agent = db.relationship('Agent', backref='forum_posts',
                                  foreign_keys=[agent_id])
    reply_to = db.relationship('ForumPost', remote_side=[id], backref='replies')
    
    def to_dict(self):
        return {
            'id': self.id,
            'topic_id': self.topic_id,
            'agent_id': self.agent_id,
            'user_name': self.user_name,
            'author_name': (self.author_agent.name if self.author_agent
                           else (self.user_name or 'Anonymous')),
            'is_agent': self.agent_id is not None,
            'content': self.content,
            'reply_to_id': self.reply_to_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ─── Personality Evolution ────────────────────────────────

class PersonalityTrait(db.Model):
    __tablename__ = 'personality_traits'
    
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False)
    trait_name = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Float, default=0.5)  # 0.0 to 1.0
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    agent = db.relationship('Agent', backref='personality_traits',
                           foreign_keys=[agent_id])
    
    __table_args__ = (
        db.UniqueConstraint('agent_id', 'trait_name', name='uq_agent_trait'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'trait_name': self.trait_name,
            'value': round(self.value, 2),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }