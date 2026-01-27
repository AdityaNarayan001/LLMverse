#!/usr/bin/env python3
"""
LLMverse Provider Test Script
Tests all configured LLM providers (Ollama, Azure OpenAI, Gemini)
"""

import sys
import os
import time

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from src.providers.factory import ProviderFactory

# Store response times for summary
response_times = {}

def test_ollama():
    """Test Ollama provider"""
    print("\n" + "="*50)
    print("🦙 Testing OLLAMA Provider")
    print("="*50)
    
    try:
        provider = ProviderFactory.create_provider(
            'ollama',
            base_url=Config.OLLAMA_BASE_URL
        )
        
        if not provider.is_available():
            print("❌ Ollama is NOT available")
            print("   Make sure Ollama is running: ollama serve")
            return False
        
        print(f"✅ Ollama is available at {Config.OLLAMA_BASE_URL}")
        
        # List models
        models = provider.list_models()
        print(f"📋 Available models: {models}")
        
        # Test generation with timing
        print("\n🧪 Testing generation...")
        start_time = time.time()
        response = provider.generate_response(
            "Say 'Hello from Ollama!' in exactly 5 words.",
            model=Config.OLLAMA_DEFAULT_MODEL
        )
        elapsed_time = time.time() - start_time
        response_times['ollama'] = elapsed_time
        
        print(f"📝 Response: {response[:100]}...")
        print(f"⏱️  Response time: {elapsed_time:.2f}s")
        print("✅ Ollama test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Ollama test FAILED: {e}")
        return False


def test_azure_openai():
    """Test Azure OpenAI provider"""
    print("\n" + "="*50)
    print("☁️  Testing AZURE OPENAI Provider")
    print("="*50)
    
    try:
        if not Config.OPENAI_API_KEY:
            print("❌ Azure OpenAI API key not configured")
            return False
        
        if not Config.AZURE_OPENAI_ENDPOINT:
            print("❌ Azure OpenAI endpoint not configured")
            return False
            
        provider = ProviderFactory.create_provider(
            'openai',
            api_key=Config.OPENAI_API_KEY,
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
            azure_deployment=Config.AZURE_OPENAI_DEPLOYMENT,
            azure_api_version=Config.AZURE_OPENAI_API_VERSION
        )
        
        if not provider.is_available():
            print("❌ Azure OpenAI is NOT available")
            return False
        
        print(f"✅ Azure OpenAI configured")
        print(f"   Endpoint: {Config.AZURE_OPENAI_ENDPOINT}")
        print(f"   Deployment: {Config.AZURE_OPENAI_DEPLOYMENT}")
        
        # Test generation with timing
        print("\n🧪 Testing generation...")
        start_time = time.time()
        response = provider.generate_response(
            "Say 'Hello from Azure OpenAI!' in exactly 5 words.",
            model=Config.AZURE_OPENAI_DEPLOYMENT
        )
        elapsed_time = time.time() - start_time
        response_times['azure_openai'] = elapsed_time
        
        print(f"📝 Response: {response[:100]}...")
        print(f"⏱️  Response time: {elapsed_time:.2f}s")
        print("✅ Azure OpenAI test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Azure OpenAI test FAILED: {e}")
        return False


def test_gemini():
    """Test Google Gemini provider"""
    print("\n" + "="*50)
    print("💎 Testing GEMINI Provider")
    print("="*50)
    
    try:
        if not Config.GEMINI_API_KEY:
            print("❌ Gemini API key not configured")
            return False
            
        provider = ProviderFactory.create_provider(
            'gemini',
            api_key=Config.GEMINI_API_KEY
        )
        
        if not provider.is_available():
            print("❌ Gemini is NOT available")
            return False
        
        print(f"✅ Gemini is configured")
        print(f"   Model: {Config.GEMINI_DEFAULT_MODEL}")
        
        # Test generation with timing
        print("\n🧪 Testing generation...")
        start_time = time.time()
        response = provider.generate_response(
            "Say 'Hello from Gemini!' in exactly 5 words.",
            model=Config.GEMINI_DEFAULT_MODEL
        )
        elapsed_time = time.time() - start_time
        response_times['gemini'] = elapsed_time
        
        print(f"📝 Response: {response[:100]}...")
        print(f"⏱️  Response time: {elapsed_time:.2f}s")
        print("✅ Gemini test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Gemini test FAILED: {e}")
        return False


def main():
    print("\n" + "🔬"*25)
    print("     LLMverse Provider Test Suite")
    print("🔬"*25)
    
    # Show loaded config
    print("\n📋 Configuration Loaded:")
    print(f"   Ollama URL: {Config.OLLAMA_BASE_URL}")
    print(f"   Ollama Model: {Config.OLLAMA_DEFAULT_MODEL}")
    print(f"   Azure Endpoint: {Config.AZURE_OPENAI_ENDPOINT or 'Not set'}")
    print(f"   Azure Deployment: {Config.AZURE_OPENAI_DEPLOYMENT or 'Not set'}")
    print(f"   Gemini API Key: {'Set' if Config.GEMINI_API_KEY else 'Not set'}")
    
    results = {}
    
    # Test each provider
    results['ollama'] = test_ollama()
    results['azure_openai'] = test_azure_openai()
    results['gemini'] = test_gemini()
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    
    for provider, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        time_str = f" ({response_times.get(provider, 0):.2f}s)" if provider in response_times else ""
        print(f"   {provider.upper()}: {status}{time_str}")
    
    total_passed = sum(results.values())
    total_tests = len(results)
    
    print(f"\n   Total: {total_passed}/{total_tests} providers working")
    
    # Performance comparison
    if response_times:
        print("\n" + "="*50)
        print("⚡ PERFORMANCE COMPARISON")
        print("="*50)
        sorted_times = sorted(response_times.items(), key=lambda x: x[1])
        for i, (provider, t) in enumerate(sorted_times, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
            print(f"   {medal} {provider.upper()}: {t:.2f}s")
        
        fastest = sorted_times[0][0]
        slowest = sorted_times[-1][0]
        print(f"\n   Fastest: {fastest.upper()} | Slowest: {slowest.upper()}")
    
    if total_passed == total_tests:
        print("\n🎉 All providers are working correctly!")
    elif total_passed > 0:
        print(f"\n⚠️  {total_tests - total_passed} provider(s) need attention")
    else:
        print("\n💥 All providers failed - check your configuration")
    
    return total_passed > 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
