from abc import ABC, abstractmethod
from typing import Dict, Any, List

class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key
        self.base_url = base_url
    
    @abstractmethod
    def generate_response(self, prompt: str, model: str = None, **kwargs) -> str:
        """Generate a response from the LLM"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and configured"""
        pass
    
    @abstractmethod
    def list_models(self) -> List[str]:
        """List available models for this provider"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of this provider"""
        pass