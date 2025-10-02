import google.generativeai as genai
from typing import List
from . import LLMProvider

class GeminiProvider(LLMProvider):
    """Google Gemini provider implementation"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key=api_key)
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            self.model = None
    
    def generate_response(self, prompt: str, model: str = "gemini-pro", **kwargs) -> str:
        """Generate response using Gemini API"""
        if not self.model:
            raise ValueError("Gemini API key not configured")
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if Gemini is available"""
        return self.model is not None
    
    def list_models(self) -> List[str]:
        """List available Gemini models"""
        return [
            "gemini-pro",
            "gemini-pro-vision"
        ]
    
    def get_provider_name(self) -> str:
        return "gemini"