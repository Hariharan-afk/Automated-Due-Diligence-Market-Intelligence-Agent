import sys
import os
from dotenv import load_dotenv
load_dotenv('.env')

sys.path.append('.')
from src.tools.hybrid_search import HybridSearchEngine
from src.config import QDRANT_CONFIG

print(f"QDRANT_URL set: {'QDRANT_URL' in os.environ}")
print(f"QDRANT_API_KEY set: {'QDRANT_API_KEY' in os.environ}")

print("Connecting to Qdrant...")
engine = HybridSearchEngine()

if engine.chunks:
    print("\n--- FIRST CHUNK METADATA ---")
    print(engine.chunks[0]['metadata'])
    
    # Check distinct source types
    sources = set()
    for chunk in engine.chunks[:100]:  # Check first 100
        if 'source_type' in chunk['metadata']:
            sources.add(chunk['metadata']['source_type'])
        elif 'source' in chunk['metadata']:
            sources.add(chunk['metadata']['source'])
            
    print("\n--- FOUND SOURCES ---")
    print(sources)
else:
    print("No chunks found in index!")
