# LLMverse - Multi-Agent LLM Simulation Platform

Multi-agent simulation platform where AI agents with unique personalities interact autonomously.

## Quick Start

```bash
# Setup
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure (add your API keys)
cp config.yaml config.local.yaml

# For Ollama (local)
ollama serve && ollama pull gemma3:270m

# Run
python start.py
# Open http://localhost:5000
```

## Project Structure

```
LLMverse/
├── app.py                  # Flask routes & Socket.IO events
├── models.py               # SQLAlchemy models (Agent, Memory, Action, Environment)
├── config.py               # YAML config loader (merges config.yaml + config.local.yaml)
├── start.py                # Entry point
├── src/
│   ├── agents/
│   │   ├── agent_manager.py    # Orchestration & simulation loop
│   │   └── llm_agent.py        # Individual agent behavior
│   ├── providers/
│   │   ├── __init__.py         # LLMProvider base class
│   │   ├── factory.py          # Provider factory
│   │   ├── ollama_provider.py
│   │   ├── openai_provider.py  # Supports Azure OpenAI
│   │   └── gemini_provider.py
│   ├── memory/
│   │   └── memory_manager.py   # Short/long-term memory
│   └── environment/
│       └── environment_manager.py
├── templates/              # Jinja2 templates
└── static/                 # CSS & JS
```

## Configuration (config.local.yaml)

```yaml
flask:
  secret_key: "your-secret-key"
  debug: true

providers:
  ollama:
    base_url: "http://localhost:11434"
    default_model: "gemma3:270m"

  openai:
    api_key: "your-azure-api-key"
    azure_endpoint: "https://your-resource.openai.azure.com/"
    azure_deployment: "your-deployment-name"
    azure_api_version: "2024-02-15-preview"

  gemini:
    api_key: "your-gemini-api-key"
    default_model: "gemini-2.5-flash-lite"
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/agents` | List/Create agents |
| PUT/DELETE | `/api/agents/<id>` | Update/Delete agent |
| POST | `/api/agents/<id>/chat` | Chat with agent |
| POST | `/api/simulation/start\|stop` | Control simulation |
| POST | `/api/environment/reset` | Reset environment |

## Database (SQLite)

| Table | Purpose |
|-------|---------|
| `agents` | name, personality, provider, model |
| `memories` | content, type (short/long), importance |
| `actions` | agent actions with metadata |
| `environment` | virtual environment state |

## License

MIT
