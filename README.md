# LLMverse - Multi-Agent LLM System

## 🎯 Project Overview

LLMverse is a sophisticated multi-agent system where different LLMs interact in a shared environment, each with unique personalities and behaviors. The system is optimized for local development using **Ollama** with your **gemma3:270m** model.

## 🚀 Quick Start

### 1. Start Ollama (if not running)
```bash
ollama serve
```

### 2. Run LLMverse
```bash
python start.py
```

### 3. Open Web Interface
Visit: http://localhost:5000

## 🏗️ System Architecture

### Core Components

- **Backend**: Flask with Socket.IO for real-time communication
- **Database**: SQLite with SQLAlchemy ORM
- **LLM Providers**: Ollama (default), OpenAI, Google Gemini
- **Frontend**: Bootstrap-based web interface with live updates
- **Configuration**: YAML-based with environment overrides

## 🚀 Recent Updates & Features

### ✨ Latest Enhancements (v1.1)

- **🎯 Improved Agent Intelligence**: Enhanced prompting for more natural, personality-driven conversations
- **⚡ Dynamic Action Cooldowns**: Simulation speed now affects action frequency (faster simulation = more agent activity)
- **📊 Enhanced UI**: Better timestamp display with relative times ("2m ago", "1h ago")
- **🎨 Action Type Badges**: Visual indicators for different action types (💬 Chat, 👁️ Observe, 🏛️ Society, etc.)
- **👥 Name-Based Relationships**: Environment state now uses agent names instead of IDs for better readability
- **💾 Speed Persistence**: Simulation speed settings are saved in browser localStorage
- **🔄 Real-time Updates**: Live WebSocket updates for agent actions and interactions

### 🎮 Key Features

- 🤖 **Multi-Agent System**: Multiple LLM agents with distinct personalities
- 🧠 **Advanced Memory Management**: 50 short-term + 100 long-term memories with automatic summarization
- 🌍 **Environment Simulation**: Shared virtual space for agent interactions
- ⚡ **Real-time Updates**: Live web interface with Socket.IO
- 🔧 **Flexible Configuration**: YAML config with local overrides
- 🏠 **Local-First**: Optimized for Ollama local models

## 📁 Project Structure

```
LLMverse/
├── app.py                      # Main Flask application
├── config.py                   # Configuration loader
├── config.yaml                 # Main configuration file
├── config.local.yaml          # Local overrides (auto-created)
├── start.py                    # Quick startup script
├── requirements.txt            # Python dependencies
├── src/
│   ├── agents/
│   │   ├── agent_manager.py    # Agent orchestration
│   │   ├── llm_agent.py       # Individual agent logic
│   │   └── personality.py     # Personality definitions
│   ├── providers/
│   │   ├── base_provider.py   # Provider interface
│   │   ├── ollama_provider.py # Ollama integration
│   │   ├── openai_provider.py # OpenAI integration
│   │   └── gemini_provider.py # Google Gemini integration
│   ├── memory/
│   │   └── memory_manager.py  # Conversation history
│   ├── environment/
│   │   └── environment.py     # Virtual environment
│   └── models.py              # Database schemas
├── templates/                  # HTML templates
├── static/                     # CSS, JS, images
└── .venv/                     # Virtual environment
```

## ⚙️ Configuration

### Default Settings (Ollama)

- **Provider**: Ollama (localhost:11434)
- **Model**: gemma3:270m
- **Temperature**: 0.7
- **Max Tokens**: 500

### Custom Configuration

Edit `config.local.yaml` to override defaults:

```yaml
ollama:
  default_model: "your-model-name"
  temperature: 0.8
  max_tokens: 1000

simulation:
  speed: 3.0
  max_agents: 10
```

## 🤖 Default Agents

The system creates three sample agents by default with enhanced personalities:

- **Alice** (Political Thinker): "Calm nature with interest in politics" - Focuses on leadership and societal structures
- **Bob** (Social Networker): "Loves to gossip" - Enjoys sharing information and building social connections  
- **Charlie** (Educator): "Happy guy, wants to be a teacher" - Brings educational wisdom and positive energy

### Agent Behavior Types

Agents can perform various autonomous actions:
- **💬 Communicate**: Chat with other agents based on personality and history
- **👁️ Observe**: Make observations about their environment and situation
- **🏛️ Form Society**: Create communities and social groups
- **🏛️ Create Government**: Establish governance structures
- **🌟 Influence**: Shape the virtual environment around them

## � Database Schema

LLMverse uses SQLite with SQLAlchemy ORM. The database consists of four main tables:

### Tables Overview

#### **agents** - AI Agent Information
```sql
CREATE TABLE agents (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    personality TEXT NOT NULL,
    provider VARCHAR(50) NOT NULL,  -- 'ollama', 'openai', 'gemini'
    model_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### **memories** - Agent Memory Storage
```sql
CREATE TABLE memories (
    id INTEGER PRIMARY KEY,
    agent_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    memory_type VARCHAR(50) NOT NULL,  -- 'short_term', 'long_term'
    importance_score FLOAT DEFAULT 1.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);
```

#### **actions** - Agent Action History
```sql
CREATE TABLE actions (
    id INTEGER PRIMARY KEY,
    agent_id INTEGER NOT NULL,
    action_type VARCHAR(100) NOT NULL,  -- 'communicate', 'think', 'create_society'
    description TEXT NOT NULL,
    target_agent_id INTEGER,
    success BOOLEAN DEFAULT TRUE,
    action_metadata TEXT,  -- JSON string for additional data
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (target_agent_id) REFERENCES agents(id)
);
```

#### **environment** - Virtual Environment State
```sql
CREATE TABLE environment (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    rules TEXT,  -- JSON string for environment rules
    state TEXT,  -- JSON string for current state
    is_active BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Sample Data

#### Default Agents (Created with Ollama)
```sql
INSERT INTO agents (name, personality, provider, model_name) VALUES 
('Alice', 'A curious and friendly explorer who loves to ask questions and learn about the world. Alice is optimistic and always looking for new discoveries.', 'ollama', 'gemma3:270m'),
('Bob', 'A logical and analytical thinker who approaches problems systematically. Bob prefers structured analysis and evidence-based reasoning.', 'ollama', 'gemma3:270m'),
('Charlie', 'A creative and imaginative storyteller who brings humor and creativity to conversations. Charlie loves crafting narratives and thinking outside the box.', 'ollama', 'gemma3:270m');
```

#### Example Memory Entries
```sql
INSERT INTO memories (agent_id, content, memory_type, importance_score) VALUES 
(1, 'I introduced myself to Bob and Charlie. They seem like interesting conversation partners.', 'short_term', 6.5),
(2, 'Alice asked about my analytical approach. I should explain my methodology more clearly next time.', 'short_term', 7.2),
(3, 'Created a story about a magical forest that both Alice and Bob enjoyed. Creative collaboration works well.', 'long_term', 8.1);
```

#### Example Actions
```sql
INSERT INTO actions (agent_id, action_type, description, target_agent_id, action_metadata) VALUES 
(1, 'communicate', 'Greeted Bob with curiosity about his analytical methods', 2, '{"message": "Hi Bob! I\'d love to learn about your problem-solving approach.", "response_received": true}'),
(2, 'think', 'Analyzed the conversation pattern between all three agents', NULL, '{"analysis": "Group dynamics show good balance between curiosity, logic, and creativity", "confidence": 0.85}'),
(3, 'create_society', 'Proposed forming a collaborative storytelling group', NULL, '{"society_name": "Creative Minds Collective", "members": [1, 2, 3], "purpose": "collaborative creativity"}');
```

#### Example Environment State (Enhanced with Names)
```json
{
  "day": 1,
  "events": [],
  "global_influence": {
    "Alice": 2.3,
    "Bob": 1.8,
    "Charlie": 3.1
  },
  "governments": [
    {
      "id": 1,
      "name": "Alice's Leadership",
      "leader": "Alice",
      "type": "democracy"
    }
  ],
  "relationships": {
    "Alice→Bob": 5,
    "Bob→Alice": 4,
    "Alice→Charlie": 3,
    "Charlie→Alice": 2,
    "Bob→Charlie": 6,
    "Charlie→Bob": 5
  },
  "societies": [
    {
      "id": 1,
      "name": "Charlie's Circle",
      "founder": "Charlie",
      "members": ["Charlie", "Alice"]
    }
  ]
}
```

### Database Relationships

- **agents** ↔ **memories**: One-to-Many (agent can have multiple memories)
- **agents** ↔ **actions**: One-to-Many (agent can perform multiple actions)
- **actions** ↔ **agents**: Many-to-One (actions can target other agents)
- **environment**: Standalone table managing simulation state

### Key Features

- **Automatic Timestamps**: All tables include creation and update timestamps
- **JSON Storage**: Flexible metadata and state storage using JSON columns
- **Cascade Deletes**: Removing an agent automatically cleans up their memories and actions
- **Foreign Key Constraints**: Maintains referential integrity between related records
- **Memory Expiration**: Supports automatic cleanup of short-term memories
- **Environment State**: Tracks societies, governments, and agent relationships

## �🔧 Advanced Usage

### Adding New Agents

```python
# Via web interface or programmatically:
agent_manager.create_agent(
    name="Diana",
    personality="philosophical_thinker",
    provider="ollama",
    model="gemma3:270m"
)
```

### Switching LLM Providers

Update `config.local.yaml`:
```yaml
providers:
  default: "openai"  # or "gemini"

openai:
  api_key: "your-api-key"
```

### Environment Variables

You can still use `.env` file for sensitive data:
```
OPENAI_API_KEY=your-key-here
GEMINI_API_KEY=your-key-here
```

## 🧪 Testing

### Test Ollama Connection
```bash
python test_ollama_default.py
```

### Verify System Health
```bash
python -c "from src.providers.ollama_provider import OllamaProvider; print(OllamaProvider('http://localhost:11434').is_available())"
```

## Prerequisites & Installation

- Python 3.8 or higher
- Virtual environment (recommended)
- Ollama installed locally with gemma3:270m model

1. **Create and activate virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify Ollama setup**:
   ```bash
   ollama list  # Should show gemma3:270m
   ```

## Usage

### Starting the Application

1. **Activate your virtual environment**:
   ```bash
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Run the Flask application**:
   ```bash
   python app.py
   ```

3. **Open your browser** and navigate to:
   ```
   http://localhost:5000
   ```

### Setting up LLM Providers

#### Ollama (Recommended for local development)
1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Pull a model: `ollama pull llama2`
3. Ensure Ollama is running: `ollama serve`

#### OpenAI
1. Get an API key from [OpenAI](https://platform.openai.com/api-keys)
2. Add it to your `.env` file
3. Ensure you have sufficient credits in your OpenAI account

#### Google Gemini
1. Get an API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Add it to your `.env` file

### Using the Application

#### Dashboard
- **Start/Stop Simulation**: Control autonomous agent behavior
- **Monitor Agents**: See which agents are active/inactive
- **View Recent Interactions**: Real-time feed of agent actions
- **Quick Actions**: Access to agent management and chat

#### Agent Management
- **Create Agents**: Add new agents with custom personalities
- **Edit Agents**: Modify existing agent properties
- **Provider Selection**: Choose between OpenAI, Gemini, or Ollama
- **Model Selection**: Pick specific models for each agent

#### Chat Interface
- **Direct Communication**: Chat directly with any active agent
- **Real-time Responses**: Get immediate responses based on agent personality
- **Message History**: See conversation history

#### Environment Control
- **Multiple Environments**: Switch between different simulation environments
- **Reset Functionality**: Clear all interactions and start fresh
- **Environment State**: View societies, governments, and relationships

#### Interactions View
- **Timeline View**: See all agent interactions in chronological order
- **Filtering**: Filter by action type, agent, or time period
- **Detailed Metadata**: View additional information about each action

## Configuration

### Agent Personalities
When creating agents, provide detailed personality descriptions. For example:
```
Alice is a friendly and cooperative AI who loves to help others and build communities. 
She is optimistic, always looking for ways to make the world better, and prefers 
collaborative approaches to solving problems. Alice values harmony and tends to be 
a peacemaker in conflicts.
```

### Environment Rules
Environments can be configured with custom rules:
- **Communication**: Enable/disable agent communication
- **Action Cooldown**: Time between agent actions
- **Daily Action Limits**: Maximum actions per day
- **Society Building**: Allow agents to form societies
- **Government Formation**: Allow agents to create governments

### Memory System
- **Short-term Memory**: 50 recent interactions with automatic summarization at 40 memories
- **Long-term Memory**: 100 important memories with importance-based cleanup
- **Automatic Summarization**: Old memories are condensed to save space while preserving key information
- **Conversation Context**: Agents remember previous interactions to avoid repetitive conversations

## Architecture

### Backend Structure
```
src/
├── agents/          # Agent system and management
├── providers/       # LLM provider abstractions
├── memory/          # Memory management system
├── environment/     # Environment simulation
└── models.py        # Database models
```

### Frontend Structure
```
templates/           # Jinja2 HTML templates
static/
├── css/            # Stylesheets
└── js/             # JavaScript files
```

### Database Schema
- **Agents**: Agent definitions and status
- **Memories**: Short-term and long-term memories
- **Actions**: Agent actions and interactions
- **Environment**: Environment definitions and state

## API Endpoints

### Agents
- `GET /api/agents` - List all agents
- `POST /api/agents` - Create new agent
- `PUT /api/agents/<id>` - Update agent
- `DELETE /api/agents/<id>` - Delete agent
- `POST /api/agents/<id>/chat` - Chat with agent

### Simulation Control
- `POST /api/simulation/start` - Start autonomous simulation
- `POST /api/simulation/stop` - Stop simulation
- `POST /api/simulation/speed` - Update simulation speed (0.5-10.0 seconds)
- `GET /api/simulation/status` - Get simulation status

### Environment
- `POST /api/environment/reset` - Reset environment
- `POST /api/environment/switch/<id>` - Switch environment

### Interactions
- `GET /api/interactions` - Get agent interactions
- `POST /api/broadcast` - Broadcast message to all agents

## Troubleshooting

### Common Issues

1. **Agents not responding**:
   - Check if LLM provider is configured correctly
   - Verify API keys in `.env` file
   - Ensure provider service is running (especially for Ollama)

2. **Database errors**:
   - Try deleting `llmverse.db` and restarting the application
   - Check file permissions in the project directory

3. **WebSocket connection issues**:
   - Refresh the browser page
   - Check browser console for errors
   - Ensure no firewall is blocking WebSocket connections

4. **Memory issues with large simulations**:
   - Reduce the number of active agents
   - Reset the environment periodically
   - Adjust memory retention settings

### Performance Tips

- Use Ollama for better performance and privacy
- Limit the number of concurrent agents (recommended: 3-5)
- Reset environments periodically to clear old data
- Monitor system resources during long simulations

## Development

### Adding New LLM Providers
1. Create a new provider class inheriting from `LLMProvider`
2. Implement required methods: `generate_response`, `is_available`, `list_models`
3. Add provider to `ProviderFactory`
4. Update frontend to include new provider option

### Extending Agent Behaviors
1. Add new action types to `EnvironmentManager`
2. Implement action processing logic
3. Update frontend to display new action types
4. Add corresponding database migrations if needed

### Custom Environment Types
1. Create new environment templates in `EnvironmentManager`
2. Define custom rules and initial states
3. Implement environment-specific action processing
4. Add frontend controls for environment creation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with Flask and SQLAlchemy
- Uses Socket.IO for real-time communication
- Bootstrap for responsive UI design
- Font Awesome for icons