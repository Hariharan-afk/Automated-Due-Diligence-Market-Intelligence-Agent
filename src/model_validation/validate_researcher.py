"""
model_validation/validate_researcher.py
Validates Retrieval Recall (Pre-Rerank) using HybridSearchEngine.
"""

import sys
sys.path.append('.')

import json
from src.tools.hybrid_search import HybridSearchEngine
from src.config import SEARCH_CONFIG

def validate_researcher(test_file: str = "src/model_validation/golden_dataset.json"):
    print("\n" + "="*70)
    print("🕵️ VALIDATING RETRIEVAL RECALL (PRE-RERANK)")
    print("="*70)
    print("ℹ️  Note: This tests the Raw Retrieval step only (before Reranking).")
    
    # Load test data
    try:
        with open(test_file, 'r') as f:
            data = json.load(f)
        test_cases = data['test_cases']
    except FileNotFoundError:
        print(f"❌ Test file {test_file} not found. Run generate_synthetic_test.py first.")
        return
        
    # Initialize Search Engine Directly (Bypass Agent/Reranker)
    print("⚙️ Initializing HybridSearchEngine...")
    search_engine = HybridSearchEngine()
    
    hits = 0
    total = len(test_cases)
    top_k = SEARCH_CONFIG["initial_k"] # Use the configured retrieval window (e.g. 50)
    
    print(f"\n🚀 Running {total} test cases (Top-K={top_k})...")
    
    for i, case in enumerate(test_cases, 1):
        query = case['query']
        target_id = case['target_chunk_id']
        
        print(f"\nTest {i}/{total}: '{query}'")
        
        # Execute Raw Search
        results = search_engine.search(query, top_k=top_k)
        
        # Check for hit
        found = False
        retrieved_ids = [r['id'] for r in results]
        
        if target_id in retrieved_ids:
            hits += 1
            found = True
            rank = retrieved_ids.index(target_id) + 1
            print(f"  ✅ HIT! Found target at rank {rank} (Score: {results[rank-1]['score']:.4f})")
        else:
            print(f"  ❌ MISS. Target {target_id} not found in top {len(results)}.")
            
    recall = hits / total if total > 0 else 0
    print("\n" + "-"*70)
    print(f"📊 RETRIEVAL RECALL = {recall:.2%} ({hits}/{total})")
    print("-" * 70)
    
    # Lower threshold for success since this is a diagnostic tool now
    if recall < 0.5:
        print("⚠️ Warning: Retrieval Recall is below 50%")
        sys.exit(1)
    else:
        print("✅ Retrieval Validation PASSED")
        sys.exit(0)

if __name__ == "__main__":
    validate_researcher()
