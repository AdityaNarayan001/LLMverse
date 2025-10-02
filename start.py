#!/usr/bin/env python3
"""
LLMverse Startup Script - Initialize and run with Ollama
"""

import os
import sys

def check_ollama():
    """Check if Ollama is available"""
    try:
        from src.providers.ollama_provider import OllamaProvider
        provider = OllamaProvider("http://localhost:11434")
        
        if provider.is_available():
            models = provider.list_models()
            print(f"✅ Ollama connected! Available models: {models}")
            return True
        else:
            print("❌ Ollama not available. Make sure it's running.")
            return False
    except Exception as e:
        print(f"❌ Error connecting to Ollama: {e}")
        return False

def initialize_database():
    """Initialize the database"""
    try:
        from app import app, db, initialize_app
        initialize_app()
        print("✅ Database initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def start_application():
    """Start the Flask application"""
    try:
        print("\n🚀 Starting LLMverse with Ollama...")
        print("📝 Configuration: Using Ollama with gemma3:270m as default")
        print("🌐 Web interface will be available at: http://localhost:5000")
        print("\n" + "="*50)
        
        from app import app
        app.run(debug=True, host='0.0.0.0', port=5000)
        
    except KeyboardInterrupt:
        print("\n👋 LLMverse stopped by user")
    except Exception as e:
        print(f"❌ Error starting application: {e}")

def main():
    """Main startup function"""
    print("🤖 LLMverse - Multi-Agent LLM System")
    print("="*40)
    print("🔧 Using Ollama with gemma3:270m as default")
    print()
    
    # Check Ollama availability
    if not check_ollama():
        print("\n💡 To start Ollama, run: ollama serve")
        sys.exit(1)
    
    # Initialize database
    if not initialize_database():
        sys.exit(1)
    
    # Start the application
    start_application()

if __name__ == '__main__':
    main()