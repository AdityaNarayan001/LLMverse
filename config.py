import os
import yaml
from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv()

class ConfigLoader:
    """Configuration loader that supports both YAML and environment variables"""
    
    def __init__(self):
        self.config_data = {}
        self.load_yaml_config()
    
    def load_yaml_config(self):
        """Load configuration from YAML files"""
        # Try to load local config first, then fall back to default config
        config_files = ['config.local.yaml', 'config.yaml']
        
        for config_file in config_files:
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        self.config_data = yaml.safe_load(f) or {}
                    print(f"Loaded configuration from {config_file}")
                    break
                except Exception as e:
                    print(f"Error loading {config_file}: {e}")
                    continue
    
    def get(self, key_path: str, default=None):
        """Get configuration value using dot notation (e.g., 'flask.secret_key')"""
        # First try environment variable (uppercase with underscores)
        env_key = key_path.upper().replace('.', '_')
        env_value = os.environ.get(env_key)
        if env_value is not None:
            return env_value
        
        # Then try YAML configuration
        keys = key_path.split('.')
        value = self.config_data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value

# Global configuration loader instance
config_loader = ConfigLoader()

class Config:
    # Flask Configuration
    SECRET_KEY = config_loader.get('flask.secret_key', 'dev-secret-key')
    FLASK_ENV = config_loader.get('flask.env', 'development')
    HOST = config_loader.get('flask.host', '127.0.0.1')
    PORT = int(config_loader.get('flask.port', 5000))
    DEBUG = config_loader.get('flask.debug', True)
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = config_loader.get('database.url', 'sqlite:///llmverse.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # LLM Provider Settings
    OPENAI_API_KEY = config_loader.get('providers.openai.api_key')
    OPENAI_DEFAULT_MODEL = config_loader.get('providers.openai.default_model', 'gpt-3.5-turbo')
    OPENAI_MAX_TOKENS = int(config_loader.get('providers.openai.max_tokens', 500))
    OPENAI_TEMPERATURE = float(config_loader.get('providers.openai.temperature', 0.7))
    
    GEMINI_API_KEY = config_loader.get('providers.gemini.api_key')
    GEMINI_DEFAULT_MODEL = config_loader.get('providers.gemini.default_model', 'gemini-pro')
    GEMINI_MAX_TOKENS = int(config_loader.get('providers.gemini.max_tokens', 500))
    GEMINI_TEMPERATURE = float(config_loader.get('providers.gemini.temperature', 0.7))
    
    OLLAMA_BASE_URL = config_loader.get('providers.ollama.base_url', 'http://localhost:11434')
    OLLAMA_DEFAULT_MODEL = config_loader.get('providers.ollama.default_model', 'llama2')
    OLLAMA_MAX_TOKENS = int(config_loader.get('providers.ollama.max_tokens', 500))
    OLLAMA_TEMPERATURE = float(config_loader.get('providers.ollama.temperature', 0.7))
    
    # Agent Configuration
    MAX_AGENTS = int(config_loader.get('agents.max_agents', 10))
    SIMULATION_SPEED = float(config_loader.get('agents.simulation_speed', 1.0))
    MEMORY_RETENTION_DAYS = int(config_loader.get('agents.memory_retention_days', 30))
    SHORT_TERM_MEMORY_LIMIT = int(config_loader.get('agents.short_term_memory_limit', 50))
    LONG_TERM_THRESHOLD = float(config_loader.get('agents.long_term_threshold', 7.0))
    AUTONOMOUS_ACTION_INTERVAL = int(config_loader.get('agents.autonomous_action_interval', 30))
    
    # Environment Settings
    DEFAULT_RULES = config_loader.get('environment.default_rules', {
        'communication': True,
        'action_cooldown': 5,
        'max_daily_actions': 100,
        'influence_decay': 0.1,
        'society_building': True,
        'governance_formation': True
    })
    
    AUTO_ADVANCE_DAY = config_loader.get('environment.simulation.auto_advance_day', False)
    DAY_DURATION_MINUTES = int(config_loader.get('environment.simulation.day_duration_minutes', 60))
    MAX_SOCIETIES = int(config_loader.get('environment.simulation.max_societies', 10))
    MAX_GOVERNMENTS = int(config_loader.get('environment.simulation.max_governments', 5))
    
    # Logging Configuration
    LOG_LEVEL = config_loader.get('logging.level', 'INFO')
    LOG_FILE = config_loader.get('logging.file', 'logs/llmverse.log')
    LOG_MAX_FILE_SIZE_MB = int(config_loader.get('logging.max_file_size_mb', 10))
    LOG_BACKUP_COUNT = int(config_loader.get('logging.backup_count', 5))
    LOG_CONSOLE_OUTPUT = config_loader.get('logging.console_output', True)
    
    # Security Settings
    SESSION_TIMEOUT_MINUTES = int(config_loader.get('security.session_timeout_minutes', 30))
    RATE_LIMIT_REQUESTS_PER_MINUTE = int(config_loader.get('security.rate_limit_requests_per_minute', 60))
    CORS_ENABLED = config_loader.get('security.cors_enabled', False)
    CORS_ORIGINS = config_loader.get('security.cors_origins', ['http://localhost:3000'])
    
    # WebSocket Configuration
    WEBSOCKET_ENABLED = config_loader.get('websocket.enabled', True)
    WEBSOCKET_PING_INTERVAL = int(config_loader.get('websocket.ping_interval', 25))
    WEBSOCKET_PING_TIMEOUT = int(config_loader.get('websocket.ping_timeout', 60))
    WEBSOCKET_MAX_CONNECTIONS = int(config_loader.get('websocket.max_connections', 100))
    
    @classmethod
    def get_provider_config(cls, provider_name: str) -> Dict[str, Any]:
        """Get configuration for a specific provider"""
        if provider_name == 'openai':
            return {
                'api_key': cls.OPENAI_API_KEY,
                'default_model': cls.OPENAI_DEFAULT_MODEL,
                'max_tokens': cls.OPENAI_MAX_TOKENS,
                'temperature': cls.OPENAI_TEMPERATURE
            }
        elif provider_name == 'gemini':
            return {
                'api_key': cls.GEMINI_API_KEY,
                'default_model': cls.GEMINI_DEFAULT_MODEL,
                'max_tokens': cls.GEMINI_MAX_TOKENS,
                'temperature': cls.GEMINI_TEMPERATURE
            }
        elif provider_name == 'ollama':
            return {
                'base_url': cls.OLLAMA_BASE_URL,
                'default_model': cls.OLLAMA_DEFAULT_MODEL,
                'max_tokens': cls.OLLAMA_MAX_TOKENS,
                'temperature': cls.OLLAMA_TEMPERATURE
            }
        return {}