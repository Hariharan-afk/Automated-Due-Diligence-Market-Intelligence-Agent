
import sys
import os
from dotenv import load_dotenv
load_dotenv()

from src.config import LLM_CONFIG
from src.tools.local_client import get_local_client

# Explicitly set credentials path to absolute path to be safe
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath("vertex-key.json")

print("Testing Gemini Connection...")

models_to_test = [
    "gemini-1.5-flash-001",
    "gemini-1.5-flash",
    "gemini-1.5-pro-001",
    "gemini-1.0-pro-001"
]

for model in models_to_test:
    print(f"\n--- Testing Model: {model} ---")
    LLM_CONFIG["provider"] = "vertex"
    LLM_CONFIG["model"] = model
    
    # Reset singleton to ensure fresh init
    import src.tools.local_client
    import src.tools.gcp_client
    src.tools.local_client._local_client = None
    src.tools.gcp_client._gcp_client = None
    
    try:
        client = get_local_client()
        response = client.chat_completion([{"role": "user", "content": "Ping"}])
        print(f"✅ Success with {model}! Response: {response}")
        break # Stop on first success
    except Exception as e:
        print(f"❌ Failed with {model}: {e}")
