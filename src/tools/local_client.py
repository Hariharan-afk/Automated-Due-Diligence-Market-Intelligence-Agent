"""
tools/local_client.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Local LLM Client (Ollama)
"""

import sys
sys.path.append('.')

from typing import List, Dict, Any
from langchain_ollama import ChatOllama, OllamaEmbeddings
from src.config import LLM_CONFIG

class LocalClient:
    """Unified client for Local LLM (Ollama)"""
    
    def __init__(self):
        self.base_url = LLM_CONFIG["base_url"]
        self.model = LLM_CONFIG["model"]
        self.embedding_model = LLM_CONFIG["embedding_model"]
        self.embeddings = OllamaEmbeddings(
            model=self.embedding_model,
            base_url=self.base_url
        )
        print(f"✅ Local Client initialized (LLM: {self.model}, Embed: {self.embedding_model})")
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding from Ollama
        
        Args:
            text: Text to embed
        
        Returns:
            List of floats
        """
        return self.embeddings.embed_query(text)
    
    def chat_completion(self, messages: List[dict], temperature: float = 0.3) -> str:
        """
        Chat completion using LangChain + Ollama
        
        Args:
            messages: List of message dicts (OpenAI format: [{"role": "user", "content": "..."}])
            temperature: Sampling temperature
        
        Returns:
            Generated text
        """
        llm = ChatOllama(
            model=self.model,
            temperature=temperature,
            base_url=self.base_url
        )
        
        # Simple conversion for robustness
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        
        lc_messages = []
        for msg in messages:
            if msg["role"] == "system":
                lc_messages.append(SystemMessage(content=msg["content"]))
            elif msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))
                
        response = llm.invoke(lc_messages)
        return response.content

# Singleton
_local_client = None

def get_local_client():
    """Get singleton client instance (Local or GCP based on config)"""
    global _local_client
    
    # Check config for provider
    if LLM_CONFIG.get("provider") == "vertex":
        from src.tools.gcp_client import get_gcp_client
        return get_gcp_client()
        
    if _local_client is None:
        _local_client = LocalClient()
    return _local_client

def get_embedding(text: str) -> List[float]:
    return get_local_client().get_embedding(text)

def chat_completion(messages: List[dict], temperature: float = 0.3) -> str:
    return get_local_client().chat_completion(messages, temperature)
