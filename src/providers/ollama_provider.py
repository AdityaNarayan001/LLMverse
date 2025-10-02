import requests
import json
from typing import List
from . import LLMProvider

class OllamaProvider(LLMProvider):
    """Ollama local LLM provider implementation"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        super().__init__(base_url=base_url)
        self.base_url = base_url.rstrip('/')
    
    def generate_response(self, prompt: str, model: str = "llama2", **kwargs) -> str:
        """Generate response using Ollama API"""
        try:
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get('temperature', 0.7),
                    "num_predict": kwargs.get('max_tokens', 500)
                }
            }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result.get('response', '')
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ollama API error: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Ollama response parsing error: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def list_models(self) -> List[str]:
        """List available Ollama models"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            return []
        except:
            return ["llama2", "mistral", "codellama"]  # Default fallback
    
    def get_provider_name(self) -> str:
        return "ollama"