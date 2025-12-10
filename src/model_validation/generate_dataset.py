"""
src/model_validation/generate_golden_dataset.py
Generates the 'Golden Dataset' by sampling real chunks from Qdrant 
and using an LLM to generate (Query, Answer) pairs.
"""

import sys
import json
import random
import os
from typing import List, Dict

# Ensure project root is in path
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv()

from qdrant_client import QdrantClient
from src.config import QDRANT_CONFIG, LLM_CONFIG
from src.tools.local_client import get_local_client
from src.utils.helpers import extract_json

def generate_golden_dataset(num_samples: int = 15, output_file: str = "src/model_validation/golden_dataset.json"):
    print(f"\n✨ Generating Golden Dataset from Qdrant ({QDRANT_CONFIG['url']})...")
    
    # 1. Connect to Qdrant
    if not QDRANT_CONFIG['url']:
        print("❌ QDRANT_URL not set.")
        return

    qdrant = QdrantClient(
        url=QDRANT_CONFIG["url"],
        api_key=QDRANT_CONFIG["api_key"]
    )
    
    # 2. Fetch chunks (Scroll)
    print("📥 Fetching chunks...")
    try:
        response, _ = qdrant.scroll(
            collection_name=QDRANT_CONFIG["collection_name"],
            limit=100, # Fetch a batch to sample from
            with_payload=True,
            with_vectors=False
        )
    except Exception as e:
        print(f"❌ Failed to connect to Qdrant: {e}")
        return

    if not response:
        print("❌ No data found in collection.")
        return

    # Filter for chunks with enough text content
    valid_points = [p for p in response if len(p.payload.get('raw_chunk', '')) > 100]
    
    # Sample random points
    selected_points = random.sample(valid_points, min(num_samples, len(valid_points)))
    print(f"🔹 Selected {len(selected_points)} chunks for generation.")
    
    # 3. Generate Q&A pairs
    client = get_local_client()
    golden_data = []
    
    for i, point in enumerate(selected_points, 1):
        chunk_text = point.payload.get('raw_chunk', '')
        metadata = point.payload
        company = metadata.get('company_name', 'Unknown')
        source = metadata.get('data_source_type', 'Unknown')
        
        print(f"   [{i}/{len(selected_points)}] Processing chunk from {company} ({source})...")
        
        prompt = f"""You are an expert financial analyst creating a Ground Truth dataset.
        Read the text below and generate a specific, difficult question (Query) and the exact answer fact (Fact).
        
        Text Chunk:
        "{chunk_text[:1000]}"
        
        Task:
        1. Create a search query that a user would ask to find this info.
        2. Extract the specific key fact/number that answers it (e.g., "$10.5 billion", "15% increase").
        
        Return ONLY a JSON object:
        {{
            "query": "The question string",
            "fact": "The specific answer string"
        }}
        """
        
        try:
            response_text = client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            # Parse
            result = extract_json(response_text)
            
            if result and "query" in result and "fact" in result:
                entry = {
                    "query_id": f"GOLD_{i:03d}_{company.upper()[:3]}",
                    "query": result["query"],
                    "expected_facts": [result["fact"]],
                    "expected_chunk_ids": [point.id],
                    "metadata": {
                        "ticker": metadata.get('ticker', 'UNKNOWN'),
                        "company": company,
                        "source": source
                    }
                }
                golden_data.append(entry)
                print(f"     ✅ Generated: {result['query']}")
            else:
                print(f"     ⚠️ Failed to parse JSON response.")
                
        except Exception as e:
            print(f"     ❌ Error: {e}")

    # 4. Save
    if golden_data:
        with open(output_file, 'w') as f:
            json.dump(golden_data, f, indent=4)
        print(f"\n🎉 Successfully saved {len(golden_data)} golden examples to {output_file}")
    else:
        print("\n❌ Failed to generate any examples.")

if __name__ == "__main__":
    generate_golden_dataset()
