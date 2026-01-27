import google.generativeai as genai
from typing import List
from . import LLMProvider

class GeminiProvider(LLMProvider):
    """Google Gemini provider implementation"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key=api_key)
        self.api_key = api_key
        self._model_cache = {}
        if api_key:
            genai.configure(api_key=api_key)
        
    def _get_model(self, model_name: str):
        """Get or create a GenerativeModel for the given model name"""
        if model_name not in self._model_cache:
            self._model_cache[model_name] = genai.GenerativeModel(model_name)
        return self._model_cache[model_name]
    
    def generate_response(self, prompt: str, model: str = "gemini-pro", **kwargs) -> str:
        """Generate response using Gemini API"""
        if not self.api_key:
            raise ValueError("Gemini API key not configured")
        
        try:
            gemini_model = self._get_model(model)
            response = gemini_model.generate_content(prompt)
            return response.text
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if Gemini is available"""
        return self.api_key is not None and len(self.api_key) > 0
    
    def list_models(self) -> List[str]:
        """List available Gemini models"""
        return [
            "gemini-pro",
            "gemini-pro-vision"
        ]
    
    def get_provider_name(self) -> str:
        return "gemini"