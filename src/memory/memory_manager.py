from datetime import datetime, timedelta
from typing import List, Dict, Any
from models import Memory, db

class MemoryManager:
    """Manages short-term and long-term memory for agents"""
    
    def __init__(self, agent_id: int):
        self.agent_id = agent_id
        self.short_term_limit = 50  # Can hold 50 conversations
        self.long_term_limit = 100  # Can hold 100 important conversations
        self.long_term_threshold = 6.0  # Importance score threshold for long-term storage
        self.summarization_threshold = 40  # When to start summarizing short-term memories
    
    def add_memory(self, content: str, memory_type: str = 'short_term', 
                   importance_score: float = 1.0, expires_in_hours: int = None) -> Memory:
        """Add a new memory"""
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        elif memory_type == 'short_term':
            expires_at = datetime.utcnow() + timedelta(hours=24)  # Short-term memories expire in 24h
        
        memory = Memory(
            agent_id=self.agent_id,
            content=content,
            memory_type=memory_type,
            importance_score=importance_score,
            expires_at=expires_at
        )
        
        db.session.add(memory)
        db.session.commit()
        
        # Cleanup old short-term memories if limit exceeded and check for summarization
        if memory_type == 'short_term':
            self._cleanup_short_term_memories()
            self._check_for_summarization()
        elif memory_type == 'long_term':
            self._cleanup_long_term_memories()
        
        return memory
    
    def get_memories(self, memory_type: str = None, limit: int = None) -> List[Memory]:
        """Retrieve memories, optionally filtered by type"""
        query = Memory.query.filter_by(agent_id=self.agent_id)
        
        if memory_type:
            query = query.filter_by(memory_type=memory_type)
        
        # Filter out expired memories
        query = query.filter(
            (Memory.expires_at.is_(None)) | (Memory.expires_at > datetime.utcnow())
        )
        
        query = query.order_by(Memory.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_relevant_memories(self, context: str, limit: int = 10) -> List[Memory]:
        """Get memories relevant to a given context (simple keyword matching)"""
        keywords = context.lower().split()
        memories = self.get_memories()
        
        # Simple relevance scoring based on keyword matches
        relevant_memories = []
        for memory in memories:
            score = 0
            memory_content = memory.content.lower()
            for keyword in keywords:
                if keyword in memory_content:
                    score += 1
            
            if score > 0:
                relevant_memories.append((memory, score))
        
        # Sort by relevance score and return top memories
        relevant_memories.sort(key=lambda x: x[1], reverse=True)
        return [memory for memory, score in relevant_memories[:limit]]
    
    def promote_to_long_term(self, memory_id: int) -> bool:
        """Promote a memory to long-term storage"""
        memory = Memory.query.get(memory_id)
        if memory and memory.agent_id == self.agent_id:
            memory.memory_type = 'long_term'
            memory.expires_at = None  # Long-term memories don't expire
            db.session.commit()
            return True
        return False
    
    def delete_memory(self, memory_id: int) -> bool:
        """Delete a specific memory"""
        memory = Memory.query.get(memory_id)
        if memory and memory.agent_id == self.agent_id:
            db.session.delete(memory)
            db.session.commit()
            return True
        return False
    
    def cleanup_expired_memories(self):
        """Remove expired memories"""
        expired_memories = Memory.query.filter(
            Memory.agent_id == self.agent_id,
            Memory.expires_at < datetime.utcnow()
        ).all()
        
        for memory in expired_memories:
            db.session.delete(memory)
        
        db.session.commit()
        return len(expired_memories)
    
    def _cleanup_short_term_memories(self):
        """Keep only the most recent short-term memories within the limit"""
        short_term_memories = Memory.query.filter_by(
            agent_id=self.agent_id,
            memory_type='short_term'
        ).order_by(Memory.created_at.desc()).all()
        
        if len(short_term_memories) > self.short_term_limit:
            # Delete oldest memories beyond the limit
            to_delete = short_term_memories[self.short_term_limit:]
            for memory in to_delete:
                # Consider promoting important memories to long-term before deletion
                if memory.importance_score >= self.long_term_threshold:
                    memory.memory_type = 'long_term'
                    memory.expires_at = None
                else:
                    db.session.delete(memory)
            
            db.session.commit()
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """Get a summary of the agent's memory"""
        short_term_count = Memory.query.filter_by(
            agent_id=self.agent_id,
            memory_type='short_term'
        ).count()
        
        long_term_count = Memory.query.filter_by(
            agent_id=self.agent_id,
            memory_type='long_term'
        ).count()
        
        return {
            'short_term_count': short_term_count,
            'long_term_count': long_term_count,
            'total_count': short_term_count + long_term_count
        }
    
    def _check_for_summarization(self):
        """Check if short-term memories need summarization"""
        short_term_count = Memory.query.filter_by(
            agent_id=self.agent_id,
            memory_type='short_term'
        ).count()
        
        if short_term_count >= self.summarization_threshold:
            print(f"[MEMORY] Agent {self.agent_id}: Triggering memory summarization ({short_term_count} memories)")
            self._summarize_memories()
    
    def _summarize_memories(self):
        """Summarize old short-term memories into condensed long-term memories"""
        # Get oldest 20 short-term memories for summarization
        old_memories = Memory.query.filter_by(
            agent_id=self.agent_id,
            memory_type='short_term'
        ).order_by(Memory.created_at.asc()).limit(20).all()
        
        if len(old_memories) < 10:  # Need at least 10 memories to summarize
            return
        
        # Group memories by type (conversations, actions, observations)
        conversations = [m for m in old_memories if "communicated" in m.content.lower() or "said" in m.content.lower()]
        actions = [m for m in old_memories if "performed action:" in m.content]
        observations = [m for m in old_memories if "observation:" in m.content.lower()]
        
        # Create summary entries
        if conversations:
            conv_summary = f"Had {len(conversations)} conversations including: " + "; ".join([m.content[:50] + "..." for m in conversations[:3]])
            self.add_memory(conv_summary, memory_type='long_term', importance_score=7.0)
        
        if actions:
            action_summary = f"Performed {len(actions)} actions including: " + "; ".join([m.content[:50] + "..." for m in actions[:3]])
            self.add_memory(action_summary, memory_type='long_term', importance_score=6.0)
        
        # Delete the old memories that were summarized
        for memory in old_memories:
            db.session.delete(memory)
        
        db.session.commit()
        print(f"[MEMORY] Agent {self.agent_id}: Summarized {len(old_memories)} memories into long-term storage")
    
    def _cleanup_long_term_memories(self):
        """Keep only important long-term memories within limit"""
        long_term_memories = Memory.query.filter_by(
            agent_id=self.agent_id,
            memory_type='long_term'
        ).order_by(Memory.importance_score.desc(), Memory.created_at.desc()).all()
        
        if len(long_term_memories) > self.long_term_limit:
            # Delete least important memories beyond the limit
            to_delete = long_term_memories[self.long_term_limit:]
            for memory in to_delete:
                db.session.delete(memory)
            db.session.commit()
            print(f"[MEMORY] Agent {self.agent_id}: Cleaned up {len(to_delete)} old long-term memories")
    
    def get_conversation_context(self, limit: int = 10) -> str:
        """Get recent conversation context for better awareness"""
        recent_conversations = Memory.query.filter(
            Memory.agent_id == self.agent_id,
            (Memory.content.like('%communicated%') | Memory.content.like('%said%'))
        ).order_by(Memory.created_at.desc()).limit(limit).all()
        
        if not recent_conversations:
            return "No recent conversations."
        
        context_lines = []
        for memory in reversed(recent_conversations):  # Show chronologically
            context_lines.append(f"- {memory.content}")
        
        return "Recent conversations:\n" + "\n".join(context_lines)