"""
model_validation/generate_synthetic_test.py
Generates synthetic test cases by reverse-engineering queries from actual Qdrant data.
"""

import sys
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv()

import json
import random
from typing import List, Dict
from qdrant_client import QdrantClient
from src.config import QDRANT_CONFIG
from src.tools.gcp_client import get_gcp_client

def generate_synthetic_data(num_samples: int = 5, output_file: str = "src/model_validation/golden_dataset.json"):
    print(f"🔄 Connecting to Qdrant: {QDRANT_CONFIG['url']}...")
    
    client = QdrantClient(
        url=QDRANT_CONFIG["url"],
        api_key=QDRANT_CONFIG["api_key"]
    )
    
    # 1. Fetch random chunks
    # We use scroll to get some points. Since we want random, we can rely on Qdrant's internal ID ordering 
    # or just take the first N if the collection is large and shuffled, 
    # but 'scroll' with a random offset isn't directly supported efficiently without knowing IDs.
    # For simplicity in this validation scope, we'll fetch a batch and pick from it.
    
    print("📥 Fetching chunks from Qdrant...")
    response = client.scroll(
        collection_name=QDRANT_CONFIG["collection_name"],
        limit=100,
        with_payload=True,
        with_vectors=False
    )
    
    points = response[0]
    if not points:
        print("❌ No data found in Qdrant collection!")
        return

    # Sample random points
    selected_points = random.sample(points, min(num_samples, len(points)))
    
    gcp_client = get_gcp_client()
    test_cases = []
    
    print(f"🤖 Generating queries for {len(selected_points)} chunks using Vertex AI...")
    
    for i, point in enumerate(selected_points, 1):
        chunk_text = point.payload.get('raw_chunk', '')
        # Fallbacks just in case
        if not chunk_text:
            chunk_text = point.payload.get('text', '')
        if not chunk_text:
            chunk_text = point.payload.get('content', '')
            
        company = point.payload.get('company_name', 'Unknown')
        
        if not chunk_text:
            print(f"⚠️ Skipping chunk {point.id}: No 'raw_chunk', 'text', or 'content' field found.")
            continue
            
        # 2. Generate Question using LLM
        prompt = f"""You are creating a validation dataset.
        Read this financial text chunk and generate a specific search query that would lead to finding this chunk.
        
        Chunk: "{chunk_text}"
        Company: "{company}"
        
        Rules:
        1. The query MUST explicitly include the company name: "{company}".
        2. The query must be answerable by the chunk.
        3. Do NOT use pronouns like "the company" or "its". Use the actual name.
        4. Return ONLY the query string. No quotes.
        
        Query:"""
        
        try:
            query = gcp_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            ).strip().replace('"', '')
            
            # Sanitize company name for ID
            safe_company = "".join(c for c in company if c.isalnum()).upper()[:10]
            if not safe_company:
                safe_company = "UNKNOWN"
            
            # 3. Generate Golden Answer
            answer_prompt = f"""You are an expert financial analyst.
            Based ONLY on the provided text chunk, write a concise, ground-truth answer to the query: "{query}"
            
            Chunk: "{chunk_text}"
            
            Rules:
            1. Be direct and factual.
            2. If the chunk doesn't fully answer, state what is known.
            3. Max 2 sentences.
            3. Max 2 sentences.
            """
            
            golden_answer = gcp_client.chat_completion(
                messages=[{"role": "user", "content": answer_prompt}],
                temperature=0.0
            ).strip()
            
            # 4. Mock Metadata for Bias Testing (Randomly assigned for now if not in Qdrant)
            sectors = ["Technology", "Finance", "Healthcare", "Energy", "Consumer Discretionary"]
            market_caps = ["Large Cap", "Mid Cap", "Small Cap"]
            
            metadata = {
                "sector": point.payload.get('sector') or random.choice(sectors),
                "market_cap": point.payload.get('market_cap') or random.choice(market_caps),
                "region": "North America"
            }

            # Use payload chunk_id if available, else point ID
            target_id = point.payload.get('chunk_id') or point.id

            test_cases.append({
                "query_id": f"{safe_company}_{i:03d}",
                "query": query,
                "target_chunk_id": target_id,
                "target_chunk_text": chunk_text[:200] + "...", 
                "company": company,
                "golden_answer": golden_answer,
                "metadata": metadata
            })
            print(f"  [{i}/{len(selected_points)}] Generated: {query}")
            
        except Exception as e:
            print(f"  ⚠️ Failed to generate for chunk {point.id}: {e}")

    # 3. Save to file
    data = {
        "generated_at": "now",
        "source": "synthetic_qdrant",
        "test_cases": test_cases
    }
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
        
    print(f"\n✅ Saved {len(test_cases)} synthetic test cases to {output_file}")

if __name__ == "__main__":
    generate_synthetic_data()
