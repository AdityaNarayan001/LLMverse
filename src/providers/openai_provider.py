import openai
from openai import AzureOpenAI
from typing import List
from . import LLMProvider
from src.utils.logger import get_logger

logger = get_logger(__name__)

class OpenAIProvider(LLMProvider):
    """OpenAI/Azure OpenAI GPT provider implementation"""
    
    def __init__(self, api_key: str = None, azure_endpoint: str = None, 
                 azure_deployment: str = None, azure_api_version: str = "2024-02-15-preview"):
        super().__init__(api_key=api_key)
        self.is_azure = azure_endpoint is not None
        self.azure_deployment = azure_deployment
        
        if self.is_azure and api_key and azure_endpoint:
            # Azure OpenAI configuration
            self.client = AzureOpenAI(
                api_key=api_key,
                api_version=azure_api_version,
                azure_endpoint=azure_endpoint
            )
            logger.info(f"Azure OpenAI initialized", extra={'context': {'endpoint': azure_endpoint}})
        elif api_key and not self.is_azure:
            # Standard OpenAI configuration
            self.client = openai.OpenAI(api_key=api_key)
            logger.info("Standard OpenAI API initialized")
        else:
            self.client = None
    
    def generate_response(self, prompt: str, model: str = "gpt-3.5-turbo", **kwargs) -> str:
        """Generate response using OpenAI/Azure API"""
        if not self.client:
            raise ValueError("OpenAI/Azure API key not configured")
        
        try:
            # For Azure, use deployment name instead of model
            model_to_use = self.azure_deployment if self.is_azure else model
            
            response = self.client.chat.completions.create(
                model=model_to_use,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get('max_tokens', 500),
                temperature=kwargs.get('temperature', 0.7)
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI/Azure API error: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if OpenAI/Azure is available"""
        return self.client is not None
    
    def list_models(self) -> List[str]:
        """List available OpenAI models"""
        if self.is_azure:
            return [self.azure_deployment] if self.azure_deployment else ["gpt-4o"]
        return [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ]
    
    def get_provider_name(self) -> str:
        return "azure-openai" if self.is_azure else "openai"