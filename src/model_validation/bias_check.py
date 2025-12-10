"""
model_validation/bias_check.py
Runs validation on the golden dataset and calculates performance metrics per slice (Sector, Market Cap).
Generates a bias report to identify underperforming groups.
"""

import sys
import json
import os
import argparse
import numpy as np
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any

# Ensure path is set
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv()

# Import Graph
from src.graph import app
from src.model_validation.metrics import compute_all_metrics

class BiasChecker:
    def __init__(self, dataset_path: str = "src/model_validation/golden_dataset.json"):
        self.dataset_path = dataset_path
        self.results = []
        self.bias_report = {}

    def load_dataset(self) -> List[Dict]:
        """Load golden dataset"""
        if not os.path.exists(self.dataset_path):
            print(f"❌ Dataset not found at {self.dataset_path}")
            return []
        
        with open(self.dataset_path, 'r') as f:
            data = json.load(f)
            return data.get("test_cases", [])

    def run_inference(self):
        """Run the full agent graph for each test case"""
        test_cases = self.load_dataset()
        print(f"🚀 Starting Bias Check on {len(test_cases)} cases...")
        
        self.results = []
        
        for i, case in enumerate(test_cases, 1):
            query = case['query']
            print(f"\n[{i}/{len(test_cases)}] Processing: {query[:50]}...")
            
            try:
                # Invoke Graph
                inputs = {"query": query}
                final_state = app.invoke(inputs)
                
                answer = final_state.get("answer", "")
                sources = final_state.get("sources", [])
                
                # Compute Metrics
                # Note: We pass 'sources' as 'retrieved_chunks' here because 'sources' in final_state 
                # usually contains the chunks used for generation. 
                # If we want ALL retrieved chunks (before synthesis), we'd need to modify graph to correct that output.
                # For now, using 'sources' is a good proxy for "effective retrieval".
                
                # To get exact retrieval hit, we check if target_chunk_id is in the sources
                retrieved_chunks = final_state.get("research_data", []) # Graph step 'researcher' output
                
                metrics = compute_all_metrics(
                    query=query,
                    answer=answer,
                    sources=sources,
                    retrieved_chunks=retrieved_chunks,
                    test_case=case
                )
                
                # Check Recall@k (Retrieval Hit)
                target_id = case.get('target_chunk_id')
                # Check in research_data (all retrieved)
                # chunks from hybrid_search have 'chunk_id' field from payload
                retrieved_ids = [str(r.get('chunk_id') or r.get('id', '')) for r in retrieved_chunks]
                # Also check in sources (used in context) - stronger signal
                used_ids = [str(s.get('chunk_id') or s.get('id', '')) for s in sources]
                
                hit = 1 if str(target_id) in retrieved_ids else 0
                used_hit = 1 if str(target_id) in used_ids else 0
                
                # Store Result
                result = {
                    "query_id": case.get("query_id"),
                    "metadata": case.get("metadata", {}),
                    "company": case.get("company"),
                    "metrics": metrics,
                    "retrieval_hit": hit,
                    "used_hit": used_hit,
                    "execution_time": 0, # TODO: Track time if needed
                    "overall_score": metrics.get("overall_score", 0)
                }
                self.results.append(result)
                print(f"   ✅ Score: {result['overall_score']:.2f} | Hit: {hit}")
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
                import traceback
                traceback.print_exc()

    def calculate_slice_metrics(self):
        """Calculate metrics aggregated by metadata slices"""
        print("\n📊 Calculating Bias Metrics...")
        
        # Slices to check
        slices = ['sector', 'market_cap']
        
        bias_report = {
            "timestamp": datetime.now().isoformat(),
            "global_metrics": self._aggregate_metrics(self.results),
            "per_slice": {},
            "per_group": {} # Flat list of all groups for easy lookup
        }
        
        for slice_key in slices:
            slice_groups = defaultdict(list)
            
            for res in self.results:
                # Get value for this slice (e.g. "Technology" or "Large Cap")
                val = res.get("metadata", {}).get(slice_key, "Unknown")
                slice_groups[val].append(res)
            
            # Compute stats for each group in this slice
            bias_report["per_slice"][slice_key] = {}
            
            for group_name, group_results in slice_groups.items():
                stats = self._aggregate_metrics(group_results)
                bias_report["per_slice"][slice_key][group_name] = stats
                
                # Also add to flat flattened map with a unique key
                # e.g. "sector:Technology" or just "Technology" if unique?
                # The mitigator uses specific IDs. Let's use the raw group name for now.
                # Ideally we want a distinct ID.
                # For compatibility with mitigator which looks for "group_id", we might need mapping.
                # For now, we'll store by name.
                bias_report["per_group"][group_name] = stats

        self.bias_report = bias_report
        return bias_report

    def _aggregate_metrics(self, results: List[Dict]) -> Dict:
        """Compute average scores for a list of results"""
        if not results:
            return {}
        
        count = len(results)
        avg_score = np.mean([r['overall_score'] for r in results])
        avg_hit = np.mean([r['retrieval_hit'] for r in results])
        avg_groundedness = np.mean([r['metrics'].get('groundedness', {}).get('score', 0) for r in results])
        
        return {
            "count": count,
            "avg_overall_score": float(avg_score),
            "avg_retrieval_hit": float(avg_hit),
            "avg_groundedness": float(avg_groundedness)
        }

    def save_report(self, output_path: str = "src/model_validation/bias_report.json"):
        """Save bias report to file"""
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(self.bias_report, f, indent=2)
        
        print(f"\n💾 Bias Report saved to {output_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="src/model_validation/golden_dataset.json", help="Input test dataset")
    parser.add_argument("--output", default="src/model_validation/bias_report.json", help="Output bias report")
    parser.add_argument("--threshold", type=float, default=0.0, help="Minimum global score to pass")
    args = parser.parse_args()
    
    checker = BiasChecker(dataset_path=args.input)
    checker.run_inference()
    report = checker.calculate_slice_metrics()
    checker.save_report(output_path=args.output)
    
    # Check against threshold
    global_score = report.get("global_metrics", {}).get("avg_overall_score", 0)
    print(f"Global Score: {global_score:.2f} (Threshold: {args.threshold})")
    
    if global_score >= args.threshold:
        sys.exit(0)
    else:
        print(f"❌ Score {global_score:.2f} below threshold {args.threshold}")
        sys.exit(1)

if __name__ == "__main__":
    main()
