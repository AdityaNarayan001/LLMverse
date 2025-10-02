from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider
from . import LLMProvider

class ProviderFactory:
    """Factory class for creating LLM providers"""
    
    @staticmethod
    def create_provider(provider_type: str, **kwargs) -> LLMProvider:
        """Create a provider instance based on type"""
        if provider_type.lower() == 'openai':
            return OpenAIProvider(api_key=kwargs.get('api_key'))
        elif provider_type.lower() == 'gemini':
            return GeminiProvider(api_key=kwargs.get('api_key'))
        elif provider_type.lower() == 'ollama':
            return OllamaProvider(base_url=kwargs.get('base_url', 'http://localhost:11434'))
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
    
    @staticmethod
    def get_available_providers() -> list:
        """Get list of available provider types"""
        return ['openai', 'gemini', 'ollama']