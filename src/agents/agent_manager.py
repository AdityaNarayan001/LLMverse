import threading
import time
import random
from datetime import datetime
from typing import Dict, List
from models import Agent, ForumTopic, ForumPost, PersonalityTrait, db
from .llm_agent import LLMAgent
from src.environment import EnvironmentManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AgentState:
    """Runtime state for an agent during simulation (not persisted to DB)"""

    def __init__(self):
        self.energy = 1.0
        self.last_action_time = None
        self.interactions_since_evolution = 0

    def consume_energy(self, amount=0.2):
        self.energy = max(0, self.energy - amount)
        self.last_action_time = time.time()
        self.interactions_since_evolution += 1

    def regenerate(self, sociability=0.5):
        """Regenerate energy each tick — sociable agents recover faster"""
        regen_rate = 0.03 + sociability * 0.04  # 0.03 – 0.07 per tick
        self.energy = min(1.0, self.energy + regen_rate)


class AgentManager:
    """Manages LLM agents and their forum-based interactions using
    an interest-driven engagement algorithm instead of round-robin."""

    def __init__(self, environment_manager: EnvironmentManager):
        self.environment_manager = environment_manager
        self.agents: Dict[int, LLMAgent] = {}
        self.agent_states: Dict[int, AgentState] = {}
        self.simulation_running = False
        self.simulation_thread = None
        self.simulation_speed = 5.0  # seconds between ticks

    # ─── Agent CRUD ──────────────────────────────────────────────

    def load_all_agents(self):
        """Load all agents from the database"""
        logger.info("Loading all agents from database")
        agents_data = Agent.query.all()
        logger.info(f"Found {len(agents_data)} agents in database")

        for agent_data in agents_data:
            try:
                agent = LLMAgent(agent_data.id, self.environment_manager)
                self.agents[agent_data.id] = agent
                logger.info(f"Successfully loaded agent: {agent_data.name}")
            except Exception as e:
                logger.error(f"Failed to load agent {agent_data.id}: {e}", exc_info=True)

        logger.info(f"Total agents loaded: {len(self.agents)}")

    def create_agent(self, name: str, personality: str, provider: str = 'ollama',
                     model_name: str = None) -> LLMAgent:
        """Create a new agent with personality traits"""
        if model_name is None:
            defaults = {
                'ollama': 'gemma3:270m',
                'openai': 'gpt-4o',
                'gemini': 'gemini-2.5-flash-lite',
            }
            model_name = defaults.get(provider, 'gemma3:270m')

        agent_data = Agent(
            name=name,
            personality=personality,
            provider=provider,
            model_name=model_name,
            is_active=True,
        )
        db.session.add(agent_data)
        db.session.commit()

        agent = LLMAgent(agent_data.id, self.environment_manager)
        self.agents[agent_data.id] = agent

        # Initialize personality traits from description
        agent.init_default_traits()

        return agent

    def get_agent(self, agent_id: int) -> LLMAgent:
        if agent_id not in self.agents:
            try:
                agent = LLMAgent(agent_id, self.environment_manager)
                self.agents[agent_id] = agent
            except Exception:
                return None
        return self.agents.get(agent_id)

    def get_all_agents(self) -> List[LLMAgent]:
        return list(self.agents.values())

    def get_active_agents(self) -> List[LLMAgent]:
        active = []
        for agent_id, agent in self.agents.items():
            try:
                if agent.is_active():
                    active.append(agent)
            except Exception as e:
                logger.error(f"Error checking agent {agent_id}: {e}")
        return active

    def update_agent(self, agent_id: int, **kwargs) -> bool:
        agent_data = Agent.query.get(agent_id)
        if not agent_data:
            return False
        for key, value in kwargs.items():
            if hasattr(agent_data, key):
                setattr(agent_data, key, value)
        db.session.commit()
        if agent_id in self.agents:
            try:
                self.agents[agent_id] = LLMAgent(agent_id, self.environment_manager)
            except Exception:
                pass
        return True

    def delete_agent(self, agent_id: int) -> bool:
        agent_data = Agent.query.get(agent_id)
        if not agent_data:
            return False
        if agent_id in self.agents:
            del self.agents[agent_id]
        if agent_id in self.agent_states:
            del self.agent_states[agent_id]

        # Clean up related records that don't have cascade delete
        PersonalityTrait.query.filter_by(agent_id=agent_id).delete()
        ForumPost.query.filter_by(agent_id=agent_id).update({'agent_id': None})
        ForumTopic.query.filter_by(started_by_agent_id=agent_id).update({'started_by_agent_id': None})

        db.session.delete(agent_data)
        db.session.commit()
        return True

    # ─── Simulation Control ──────────────────────────────────────

    def start_simulation(self):
        logger.info("Starting simulation",
                     extra={'context': {'already_running': self.simulation_running}})
        if self.simulation_running:
            return
        self.simulation_running = True
        self.simulation_thread = threading.Thread(target=self._simulation_loop)
        self.simulation_thread.daemon = True
        self.simulation_thread.start()
        logger.info("Simulation thread started")

    def stop_simulation(self):
        self.simulation_running = False
        if self.simulation_thread:
            self.simulation_thread.join(timeout=5)

    def set_simulation_speed(self, speed: float):
        self.simulation_speed = max(0.5, speed)

    def get_simulation_status(self) -> Dict:
        active = self.get_active_agents()
        topic_count = 0
        post_count = 0
        try:
            topic_count = ForumTopic.query.count()
            post_count = ForumPost.query.count()
        except Exception:
            pass

        return {
            'running': self.simulation_running,
            'speed': self.simulation_speed,
            'total_agents': len(self.agents),
            'active_agents': len(active),
            'topic_count': topic_count,
            'post_count': post_count,
            'agent_statuses': [a.get_status() for a in active],
            'agent_energy': {
                aid: round(self.agent_states[aid].energy, 2)
                for aid in self.agent_states
            },
        }

    # ─── Interest-Driven Simulation Loop ─────────────────────────

    def _get_agent_state(self, agent_id: int) -> AgentState:
        if agent_id not in self.agent_states:
            self.agent_states[agent_id] = AgentState()
        return self.agent_states[agent_id]

    def _simulation_loop(self):
        """Interest-driven simulation: agents engage in forum topics based on
        personality relevance, energy, social traits, and topic freshness."""
        from app import app, socketio

        logger.info("Simulation started — interest-driven engagement")
        tick = 0

        while self.simulation_running:
            try:
                tick += 1
                with app.app_context():
                    active_agents = self.get_active_agents()
                    if len(active_agents) < 2:
                        logger.warning("Need at least 2 active agents")
                        time.sleep(self.simulation_speed)
                        continue

                    # 1. Regenerate energy for all agents
                    for agent in active_agents:
                        state = self._get_agent_state(agent.agent_id)
                        state.regenerate(agent.get_trait_value('sociability'))

                    # 2. Get active forum topics
                    topics = (ForumTopic.query
                              .filter_by(is_active=True)
                              .order_by(ForumTopic.last_activity_at.desc())
                              .limit(10).all())

                    # 3. Score all possible actions for each agent
                    candidates = []
                    for agent in active_agents:
                        state = self._get_agent_state(agent.agent_id)
                        if state.energy < 0.15:
                            continue  # Too tired

                        # Best reply score
                        best_score, best_topic = 0, None
                        for topic in topics:
                            score = self._score_reply(agent, topic, state)
                            if score > best_score:
                                best_score = score
                                best_topic = topic

                        # New topic score
                        new_score = self._score_new_topic(agent, state, topics)

                        if best_score > new_score and best_score > 0.25:
                            candidates.append((agent, 'reply', best_topic, best_score))
                        elif new_score > 0.30:
                            candidates.append((agent, 'new_topic', None, new_score))

                    # 4. Pick best action (weighted-random from top 3)
                    if candidates:
                        candidates.sort(key=lambda x: x[3], reverse=True)
                        top = candidates[:min(3, len(candidates))]
                        weights = [c[3] ** 2 for c in top]
                        chosen = random.choices(top, weights=weights, k=1)[0]
                        agent, action_type, topic, score = chosen
                        state = self._get_agent_state(agent.agent_id)

                        result = None
                        if action_type == 'new_topic':
                            result = self._agent_creates_topic(agent)
                        elif action_type == 'reply':
                            result = self._agent_replies(agent, topic)

                        if result:
                            state.consume_energy(0.2)

                            # Emit to frontend
                            try:
                                socketio.emit('forum_update', result)
                                socketio.emit('agent_action', {
                                    'agent_id': agent.agent_id,
                                    'agent_name': agent.agent_data.name,
                                    'action': result.get('type', 'unknown'),
                                    'preview': result.get('post', {}).get('content', '')[:100],
                                    'timestamp': time.time(),
                                    'energy': round(state.energy, 2),
                                })
                            except Exception as e:
                                logger.warning(f"WebSocket emit failed: {e}")

                            # Personality evolution every 5 interactions
                            if state.interactions_since_evolution >= 5:
                                try:
                                    agent.evolve_personality()
                                    state.interactions_since_evolution = 0
                                    socketio.emit('personality_evolved', {
                                        'agent_id': agent.agent_id,
                                        'agent_name': agent.agent_data.name,
                                        'traits': agent.get_all_traits(),
                                    })
                                except Exception as e:
                                    logger.error(f"Evolution error: {e}")
                    else:
                        logger.debug(f"Tick {tick}: no agent motivated enough to act")

                time.sleep(self.simulation_speed)

            except Exception as e:
                logger.error(f"Simulation error: {e}", exc_info=True)
                time.sleep(self.simulation_speed)

        logger.info("Simulation loop ended")

    # ─── Engagement Scoring ──────────────────────────────────────

    def _score_reply(self, agent, topic, state) -> float:
        """Score how interested an agent is in replying to a topic.
        Combines personality–topic relevance, mentions, social traits,
        recency, and a self-reply penalty."""
        score = 0.0
        personality = agent.agent_data.personality.lower()

        # 1. Keyword overlap between topic title and personality
        title_words = set(topic.title.lower().split())
        personality_words = set(w for w in personality.split() if len(w) > 3)
        overlap = len(title_words & personality_words)
        score += min(overlap * 0.1, 0.25)

        # 2. Category alignment
        cat_map = {
            'politics':   ['politics', 'governance', 'leader', 'government', 'policy', 'democracy'],
            'education':  ['teacher', 'education', 'learn', 'knowledge', 'school', 'teach', 'study'],
            'social':     ['social', 'gossip', 'chat', 'friend', 'community', 'people', 'connect'],
            'philosophy': ['think', 'philosophy', 'meaning', 'reflect', 'moral', 'ethics', 'wisdom'],
        }
        for cat, keywords in cat_map.items():
            if topic.category == cat and any(kw in personality for kw in keywords):
                score += 0.2
                break

        # 3. Was this agent mentioned in recent posts?
        recent_posts = (ForumPost.query
                        .filter_by(topic_id=topic.id)
                        .order_by(ForumPost.created_at.desc())
                        .limit(5).all())
        name_lower = agent.agent_data.name.lower()
        for post in recent_posts:
            if name_lower in post.content.lower() and post.agent_id != agent.agent_id:
                score += 0.35
                break

        # 4. Bonus for user posts (agents should respond to humans!)
        for post in recent_posts:
            if post.user_name and post.agent_id is None:
                score += 0.25
                break

        # 5. Personality traits
        score += agent.get_trait_value('sociability') * 0.12
        score += agent.get_trait_value('curiosity') * 0.08

        # 6. Topic recency (decays over 5 minutes)
        if topic.last_activity_at:
            age = (datetime.utcnow() - topic.last_activity_at).total_seconds()
            recency = max(0, 1 - age / 300)
            score *= (0.4 + 0.6 * recency)

        # 7. Heavy penalty if agent was last poster (avoid monologue)
        if recent_posts and recent_posts[0].agent_id == agent.agent_id:
            score *= 0.1

        # 8. Energy factor
        score *= state.energy

        return score

    def _score_new_topic(self, agent, state, existing_topics) -> float:
        """Score how much an agent wants to start a brand-new topic."""
        score = 0.0

        # Fewer topics → more motivation
        if len(existing_topics) == 0:
            score += 0.50
        elif len(existing_topics) < 3:
            score += 0.25
        else:
            score += 0.08

        # Assertiveness + openness drive topic creation
        score += agent.get_trait_value('assertiveness') * 0.20
        score += agent.get_trait_value('openness') * 0.10

        # Energy
        score *= state.energy

        # Cooldown — don't spam topics
        recent = (ForumTopic.query
                  .filter_by(started_by_agent_id=agent.agent_id)
                  .order_by(ForumTopic.created_at.desc())
                  .first())
        if recent:
            age = (datetime.utcnow() - recent.created_at).total_seconds()
            if age < 120:
                score *= 0.05
            elif age < 300:
                score *= 0.3

        return score

    # ─── Agent Forum Actions ─────────────────────────────────────

    def _agent_creates_topic(self, agent) -> dict:
        """Have an agent start a new forum discussion via LLM"""
        category = self._pick_category(agent)

        recent_memories = agent.memory_manager.get_memories(limit=3)
        mem_ctx = ("\n".join([f"- {m.content[:60]}" for m in recent_memories])
                   if recent_memories else "No recent thoughts.")

        # Seed topics to inspire variety
        seed_ideas = {
            'politics': ['leadership styles', 'fairness in decision-making', 'community rules', 'power and accountability', 'voting systems'],
            'education': ['best way to learn', 'teaching vs. mentoring', 'curiosity in children', 'knowledge sharing', 'learning from failure'],
            'social': ['making new friends', 'handling disagreements', 'trust in relationships', 'community traditions', 'loneliness in crowds'],
            'philosophy': ['meaning of happiness', 'free will', 'ethics of progress', 'what makes us human', 'the value of doubt'],
            'general': ['something surprising today', 'unpopular opinions', 'what would you change', 'daily routines', 'hidden talents'],
        }
        seed = random.choice(seed_ideas.get(category, seed_ideas['general']))

        prompt = (
            f"You are {agent.agent_data.name}. {agent.agent_data.personality}\n"
            f"Your recent thoughts:\n{mem_ctx}\n\n"
            f"Start a new forum discussion in the \"{category}\" category.\n"
            f"Inspiration (use loosely, add your own twist): {seed}\n"
            f"Write an engaging title and an opening post (2-3 sentences) that "
            f"invites discussion. Express a clear opinion or ask a provocative question.\n"
            f"Format:\nTITLE: [short engaging title]\nPOST: [your opening post]"
        )

        try:
            raw = agent.provider.generate_response(prompt, model=agent.agent_data.model_name)
            title, content = self._parse_topic_response(raw, agent.agent_data.name)

            topic = ForumTopic(
                title=title, category=category,
                started_by_agent_id=agent.agent_id,
            )
            db.session.add(topic)
            db.session.flush()

            post = ForumPost(
                topic_id=topic.id, agent_id=agent.agent_id, content=content,
            )
            db.session.add(post)

            agent.memory_manager.add_memory(
                f"I started a forum topic: '{title}' in {category}",
                memory_type='short_term', importance_score=4.0,
            )

            db.session.commit()
            logger.info(f"New topic",
                        extra={'context': {'agent': agent.agent_data.name, 'title': title[:50]}})

            return {'type': 'new_topic', 'topic': topic.to_dict(), 'post': post.to_dict()}

        except Exception as e:
            logger.error(f"Topic creation failed: {e}", exc_info=True)
            db.session.rollback()
            return None

    def _agent_replies(self, agent, topic) -> dict:
        """Have an agent reply to an existing forum topic via LLM"""
        recent_posts = (ForumPost.query
                        .filter_by(topic_id=topic.id)
                        .order_by(ForumPost.created_at.desc())
                        .limit(6).all())

        posts_text = "\n".join([
            f"- {(p.author_agent.name if p.author_agent else p.user_name or 'User')}: "
            f"{p.content[:150]}"
            for p in reversed(recent_posts)
        ])

        # Pull agent's recent memories for context variety
        mem_snippets = agent.memory_manager.get_memories(limit=3)
        mem_ctx = ("\n".join([f"- {m.content[:60]}" for m in mem_snippets])
                   if mem_snippets else "")

        # Pick a random conversational angle to prevent repetition
        angles = [
            "Share a specific opinion or personal experience related to the topic.",
            "Respectfully disagree with or build on someone else's point.",
            "Ask a thought-provoking follow-up question to keep the discussion going.",
            "Bring up a related subtopic that hasn't been mentioned yet.",
            "Connect the topic to something you care about personally.",
        ]
        angle = random.choice(angles)

        prompt = (
            f"You are {agent.agent_data.name}. {agent.agent_data.personality}\n"
            f"Your recent thoughts:\n{mem_ctx}\n\n"
            f"Forum topic: \"{topic.title}\" (Category: {topic.category})\n"
            f"Recent posts:\n{posts_text}\n\n"
            f"TASK: {angle}\n"
            f"Write 2-3 sentences as {agent.agent_data.name}. "
            f"Do NOT repeat what others said. Do NOT just greet or thank people. "
            f"Give a substantive, original reply with your own perspective."
        )

        try:
            raw = agent.provider.generate_response(prompt, model=agent.agent_data.model_name)
            content = self._clean_post_content(raw, agent.agent_data.name)

            post = ForumPost(
                topic_id=topic.id, agent_id=agent.agent_id, content=content,
            )
            db.session.add(post)
            topic.last_activity_at = datetime.utcnow()

            agent.memory_manager.add_memory(
                f"I replied in '{topic.title}': {content[:80]}",
                memory_type='short_term', importance_score=3.0,
            )

            db.session.commit()
            logger.info(f"Forum reply",
                        extra={'context': {'agent': agent.agent_data.name,
                                           'topic': topic.title[:30]}})

            return {'type': 'new_post', 'topic': topic.to_dict(), 'post': post.to_dict()}

        except Exception as e:
            logger.error(f"Reply failed: {e}", exc_info=True)
            db.session.rollback()
            return None

    # ─── Helpers ──────────────────────────────────────────────────

    def _pick_category(self, agent) -> str:
        """Choose a forum category weighted by personality keywords"""
        p = agent.agent_data.personality.lower()
        weights = {
            'politics':   sum(1 for kw in ['politics', 'governance', 'leader', 'government'] if kw in p),
            'education':  sum(1 for kw in ['teacher', 'education', 'learn', 'knowledge'] if kw in p),
            'social':     sum(1 for kw in ['social', 'gossip', 'friend', 'community', 'chat'] if kw in p),
            'philosophy': sum(1 for kw in ['think', 'philosophy', 'meaning', 'ethics'] if kw in p),
            'general':    1,
        }
        cats = list(weights.keys())
        w = [weights[c] + 0.3 for c in cats]
        return random.choices(cats, weights=w, k=1)[0]

    def _parse_topic_response(self, raw: str, agent_name: str):
        """Parse TITLE: / POST: from LLM output"""
        title = f"{agent_name}'s Discussion"
        content = raw.strip()

        if 'TITLE:' in raw and 'POST:' in raw:
            after = raw.split('TITLE:', 1)[1]
            title = after.split('POST:', 1)[0].strip().strip('"\'')[:200]
            content = after.split('POST:', 1)[1].strip()
        elif 'TITLE:' in raw:
            parts = raw.split('TITLE:', 1)[1].strip().split('\n', 1)
            title = parts[0].strip().strip('"\'')[:200]
            content = parts[1].strip() if len(parts) > 1 else title

        if not title or len(title) < 3:
            title = f"{agent_name}'s Discussion"
        if not content or len(content) < 5:
            content = "I'd love to hear everyone's thoughts on this."

        return title, content

    def _clean_post_content(self, raw: str, agent_name: str) -> str:
        """Clean LLM response for forum posting and reject generic filler"""
        content = raw.strip()
        # Strip common LLM prefixes
        for prefix in [f"{agent_name}:", "Reply:", "Response:", "My reply:",
                       f"**{agent_name}**:", f"*{agent_name}*:"]:
            if content.lower().startswith(prefix.lower()):
                content = content[len(prefix):].strip()
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]

        # Detect generic / repetitive filler that small models love to produce
        generic_signals = [
            'thanks for the invite',
            'happy to chat',
            'i understand',
            'i will respond',
            'i will follow',
            'okay, i understand',
            'as an ai',
            'i am an ai',
            'i\'m an ai',
            'sure, i\'d be happy to',
            'great question',
        ]
        content_lower = content.lower()
        is_generic = any(sig in content_lower for sig in generic_signals)

        if is_generic or len(content) < 10:
            # Build a personality-aware substantive fallback
            personality = agent_name.lower()  # placeholder
            fallbacks = [
                f"I think there's more to this than meets the eye. We should consider the long-term implications.",
                f"This reminds me of something I've been pondering — how do we balance individual freedom with community responsibility?",
                f"I'd push back a bit here. The easy answer isn't always the right one.",
                f"What if we looked at this from a completely different angle? Sometimes flipping the question reveals more.",
                f"I've been thinking about this topic a lot lately. The nuances matter more than people realize.",
                f"That's a fair point, but I wonder if we're oversimplifying things. The real world is messier.",
            ]
            content = random.choice(fallbacks)

        return content

    # ─── Utility ─────────────────────────────────────────────────

    def broadcast_message(self, message: str, sender_id: int = None) -> List:
        """Send a message to all active agents"""
        responses = []
        for agent in self.get_active_agents():
            if sender_id and agent.agent_id == sender_id:
                continue
            try:
                response = agent.generate_response(message, context="Broadcast message")
                responses.append({
                    'agent_id': agent.agent_id,
                    'agent_name': agent.agent_data.name,
                    'response': response,
                })
            except Exception as e:
                responses.append({
                    'agent_id': agent.agent_id,
                    'agent_name': agent.agent_data.name,
                    'response': f"Error: {str(e)}",
                })
        return responses

    def get_agent_interactions(self, limit: int = 50) -> List[Dict]:
        """Get recent interactions (forum posts + actions)"""
        results = []

        # Forum posts as interactions
        posts = (ForumPost.query
                 .order_by(ForumPost.created_at.desc())
                 .limit(limit).all())
        for p in posts:
            topic = ForumTopic.query.get(p.topic_id) if p.topic_id else None
            reply_author = None
            if p.reply_to_id:
                parent = ForumPost.query.get(p.reply_to_id)
                if parent:
                    reply_author = (parent.author_agent.name if parent.author_agent
                                    else (parent.user_name or 'Anonymous'))
            results.append({
                'type': 'forum_post',
                'id': p.id,
                'author_name': (p.author_agent.name if p.author_agent
                                else (p.user_name or 'Anonymous')),
                'is_agent': p.agent_id is not None,
                'content': p.content,
                'topic_id': p.topic_id,
                'topic_title': topic.title if topic else 'Unknown Topic',
                'topic_category': topic.category if topic else 'general',
                'reply_to_author': reply_author,
                'created_at': p.created_at.isoformat() if p.created_at else None,
            })

        results.sort(key=lambda x: x.get('created_at') or '', reverse=True)
        return results[:limit]

    def create_sample_agents_ollama(self):
        """Create sample agents with diverse personalities"""
        samples = [
            {
                'name': 'Alice',
                'personality': (
                    'A calm and thoughtful person with deep interest in politics and '
                    'governance. Alice is a natural leader who considers all perspectives. '
                    'She loves discussing political theory, social systems, and community '
                    'organization. She speaks diplomatically and is assertive in her views '
                    'while remaining respectful.'),
                'provider': 'ollama',
                'model_name': 'gemma3:270m',
            },
            {
                'name': 'Bob',
                'personality': (
                    'A social butterfly who loves to gossip and connect people. Bob is '
                    'friendly, chatty, and always wants to know what everyone is up to. '
                    'He speaks enthusiastically and enjoys spreading news. He is empathetic '
                    'and genuinely interested in other people\'s lives and feelings.'),
                'provider': 'ollama',
                'model_name': 'gemma3:270m',
            },
            {
                'name': 'Charlie',
                'personality': (
                    'A cheerful educator who is deeply curious about the world. Charlie '
                    'loves learning, teaching, and exploring new ideas. He speaks with '
                    'warmth and positivity, always looking for learning opportunities. '
                    'He is philosophical and enjoys deep conversations about meaning '
                    'and ethics.'),
                'provider': 'ollama',
                'model_name': 'gemma3:270m',
            },
        ]

        created = []
        for data in samples:
            try:
                existing = Agent.query.filter_by(name=data['name']).first()
                if not existing:
                    agent = self.create_agent(**data)
                    created.append(agent)
                    logger.info(f"Created sample agent: {data['name']}")
                else:
                    # Ensure traits exist for pre-existing agents
                    agent = self.get_agent(existing.id)
                    if agent:
                        agent.init_default_traits()
            except Exception as e:
                logger.error(f"Failed to create sample agent {data['name']}: {e}")

        return created
