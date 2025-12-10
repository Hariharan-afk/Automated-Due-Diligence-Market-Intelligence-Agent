"""
tools/gcp_client.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GCP Vertex AI Client - Embeddings + LLM
"""

import sys
sys.path.append('.')

from typing import List
import vertexai
from vertexai.language_models import TextEmbeddingModel
from vertexai.generative_models import GenerativeModel
from src.config import GCP_PROJECT_ID, GCP_LOCATION, EMBEDDING_CONFIG, AGENT_CONFIG

# Initialize Vertex AI
vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)

class GCPClient:
    """Unified client for GCP Vertex AI"""
    
    def __init__(self):
        import os
        print(f"DEBUG: GCP_PROJECT_ID={GCP_PROJECT_ID}")
        print(f"DEBUG: GOOGLE_APPLICATION_CREDENTIALS={os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")
        print(f"DEBUG: EMBEDDING_MODEL={EMBEDDING_CONFIG['model']}")
        print(f"DEBUG: LLM_MODEL={AGENT_CONFIG['planner']['model']}")
        
        self.embedding_model = TextEmbeddingModel.from_pretrained(
            EMBEDDING_CONFIG["model"]
        )
        self.chat_model = GenerativeModel(
            AGENT_CONFIG["planner"]["model"]
        )
        print(f"✅ GCP Client initialized (Project: {GCP_PROJECT_ID})")
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding from Vertex AI
        
        Args:
            text: Text to embed
        
        Returns:
            List of floats (768 dimensions)
        """
        embeddings = self.embedding_model.get_embeddings([text])
        return embeddings[0].values
    
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings in batches (more efficient)"""
        batch_size = 5
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            embeddings = self.embedding_model.get_embeddings(batch)
            all_embeddings.extend([emb.values for emb in embeddings])
        
        return all_embeddings
    
    def chat_completion(self, messages: List[dict], temperature: float = 0.3) -> str:
        """
        Chat completion using Gemini
        
        Args:
            messages: List of message dicts (OpenAI format)
            temperature: Sampling temperature
        
        Returns:
            Generated text
        """
        # Convert OpenAI format to Gemini format
        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                prompt += f"{msg['content']}\n\n"
            elif msg["role"] == "user":
                prompt += msg["content"]
        
        # Retry logic for Rate Limits (429)
        max_retries = 5
        base_delay = 5
        
        import time
        from google.api_core.exceptions import ResourceExhausted
        
        for attempt in range(max_retries + 1):
            try:
                response = self.chat_model.generate_content(
                    prompt,
                    generation_config={"temperature": temperature}
                )
                return response.text
                
            except ResourceExhausted as e:
                if attempt == max_retries:
                    print(f"❌ Rate limit exceeded after {max_retries} retries.")
                    raise e
                
                wait_time = base_delay * (2 ** attempt)  # Exponential backoff
                print(f"⚠️ Rate limit hit. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
                
            except Exception as e:
                # Re-raise other errors immediately
                raise e

# Singleton
_gcp_client = None

def get_gcp_client():
    """Get singleton GCP client instance"""
    global _gcp_client
    if _gcp_client is None:
        _gcp_client = GCPClient()
    return _gcp_client

# OpenAI-compatible interface
def get_embedding(text: str) -> List[float]:
    return get_gcp_client().get_embedding(text)

def chat_completion(messages: List[dict], temperature: float = 0.3) -> str:
    return get_gcp_client().chat_completion(messages, temperature)