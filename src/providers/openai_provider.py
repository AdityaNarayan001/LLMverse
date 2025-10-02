import openai
from typing import List
from . import LLMProvider

class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider implementation"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key=api_key)
        self.client = openai.OpenAI(api_key=api_key) if api_key else None
    
    def generate_response(self, prompt: str, model: str = "gpt-3.5-turbo", **kwargs) -> str:
        """Generate response using OpenAI API"""
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get('max_tokens', 500),
                temperature=kwargs.get('temperature', 0.7)
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if OpenAI is available"""
        return self.client is not None
    
    def list_models(self) -> List[str]:
        """List available OpenAI models"""
        return [
            "gpt-3.5-turbo",
            "gpt-4",
            "gpt-4-turbo-preview",
            "gpt-3.5-turbo-16k"
        ]
    
    def get_provider_name(self) -> str:
        return "openai"