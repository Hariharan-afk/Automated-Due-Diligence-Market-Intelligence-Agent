"""
model_validation/validate_researcher.py
Validates ResearcherAgent using synthetic ground truth (Recall@k).
"""

import sys
sys.path.append('.')

import json
import numpy as np
from src.agents.researcher_agent import ResearcherAgent
from src.tools.hybrid_search import HybridSearchEngine
from src.tools.reranker import Reranker

def validate_researcher(test_file: str = "src/model_validation/test_dataset.json"):
    print("\n" + "="*70)
    print("🕵️ VALIDATING RESEARCHER AGENT (RECALL TEST)")
    print("="*70)
    
    # Load test data
    try:
        with open(test_file, 'r') as f:
            data = json.load(f)
        test_cases = data['test_cases']
    except FileNotFoundError:
        print(f"❌ Test file {test_file} not found. Run generate_synthetic_test.py first.")
        return
        
    # Initialize Agent
    print("⚙️ Initializing Researcher Agent...")
    search_engine = HybridSearchEngine()
    reranker = Reranker()
    researcher = ResearcherAgent(search_engine, reranker)
    
    hits = 0
    total = len(test_cases)
    
    print(f"\n🚀 Running {total} test cases...")
    
    for i, case in enumerate(test_cases, 1):
        query = case['query']
        target_id = case['target_chunk_id']
        
        print(f"\nTest {i}/{total}: '{query}'")
        
        # Execute Researcher (simulate receiving sub-queries)
        # We pass it as a single sub-query list
        results = researcher.execute([query])
        
        # Check for hit
        found = False
        retrieved_ids = [r['id'] for r in results]
        
        if target_id in retrieved_ids:
            hits += 1
            found = True
            rank = retrieved_ids.index(target_id) + 1
            print(f"  ✅ HIT! Found target at rank {rank}")
        else:
            print(f"  ❌ MISS. Target {target_id} not found in top {len(results)}.")
            
    recall = hits / total if total > 0 else 0
    print("\n" + "-"*70)
    print(f"📊 RESULTS: Recall@{len(results)} = {recall:.2%} ({hits}/{total})")
    print("-"*70)
    
    if recall < 0.5:
        print("❌ Validation FAILED (Recall < 50%)")
        sys.exit(1)
    else:
        print("✅ Validation PASSED")
        sys.exit(0)

if __name__ == "__main__":
    validate_researcher()
