"""
validation/run_validation.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Main Validation Pipeline - Runs full evaluation
"""

import sys
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv()

import json
import time
from datetime import datetime
from typing import List, Dict
import numpy as np

# Import our modules
from src.model_validation.test_dataset import TestDataset
from src.model_validation.metrics import compute_all_metrics

# Import agent system
from src.agents.analyser_agent import AnalyserAgent
from src.agents.researcher_agent import ResearcherAgent
from src.agents.synthesiser_agent import SynthesiserAgent
from src.tools.hybrid_search import HybridSearchEngine
from src.tools.reranker import Reranker


class NumpyEncoder(json.JSONEncoder):
    """Custom encoder for numpy data types"""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super(NumpyEncoder, self).default(obj)

class ValidationPipeline:
    """Run complete validation on agent system"""
    
    def __init__(self, test_dataset_path: str = None):
        print("\n" + "="*70)
        print("🔬 INITIALIZING VALIDATION PIPELINE")
        print("="*70)
        
        # Load test dataset
        if test_dataset_path:
            self.test_cases = TestDataset.load_from_file(test_dataset_path)
        else:
            dataset = TestDataset()
            self.test_cases = dataset.get_test_cases()
        
        print(f"✅ Loaded {len(self.test_cases)} test cases")
        
        # Import Graph
        try:
            from src.graph import app
            self.graph_app = app
            print("✅ Agent Graph loaded")
        except ImportError as e:
            print(f"❌ Failed to load Agent Graph: {e}")
            raise

        # Results storage
        self.results = []
        
    def run_single_test(self, test_case: Dict) -> Dict:
        """
        Run agent graph on single test case and evaluate
        """
        query_id = test_case['query_id']
        query = test_case['query']
        
        print(f"\n{'─'*70}")
        print(f"🧪 Test Case: {query_id}")
        print(f"📝 Query: {query}")
        print(f"{'─'*70}")
        
        start_time = time.time()
        
        try:
            # Invoke Graph
            print("\n🤖 Invoking Agent Graph...")
            final_state = self.graph_app.invoke({"query": query})
            
            answer = final_state.get('answer', "")
            sources = final_state.get('sources', [])
            confidence = final_state.get('confidence', 0.0)
            retrieved_chunks = final_state.get('research_data', [])
            
            elapsed_time = time.time() - start_time
            
            # Compute metrics (rule-based)
            print("\n📊 Computing metrics...")
            metrics = compute_all_metrics(
                query=query,
                answer=answer,
                sources=sources,
                retrieved_chunks=retrieved_chunks,
                test_case=test_case
            )
            
            # Add metadata
            metrics['execution_time'] = elapsed_time
            metrics['agent_confidence'] = confidence
            metrics['num_retrieved_chunks'] = len(retrieved_chunks)
            metrics['num_sources'] = len(sources)
            metrics['status'] = 'success'
            metrics['hallucination_score'] = final_state.get('hallucination_score', 0.0)
            metrics['iterations'] = final_state.get('iteration', 1)
            
            # Check for retrieval hit (Recall@k)
            target_chunk_id = test_case.get('target_chunk_id')
            if target_chunk_id:
                # Check both research_data (all candidates) and sources (final used)
                # chunks from hybrid_search have 'chunk_id' field from payload
                retrieved_ids = [str(c.get('chunk_id') or c.get('id', '')) for c in retrieved_chunks]
                metrics['retrieval_hit'] = 1 if str(target_chunk_id) in retrieved_ids else 0
            
            print(f"\n✅ Test completed in {elapsed_time:.2f}s")
            print(f"📈 Overall Score: {metrics['overall_score']:.2%}")
            if 'retrieval_hit' in metrics:
                hit_str = "HIT" if metrics['retrieval_hit'] else "MISS"
                print(f"🎯 Retrieval: {hit_str}")
            
            return metrics
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            elapsed_time = time.time() - start_time
            
            return {
                'query_id': query_id,
                'query': query,
                'status': 'failed',
                'error': str(e),
                'execution_time': elapsed_time,
                'overall_score': 0.0
            }
    
    def run_all_tests(self, limit: int = None) -> List[Dict]:
        """
        Run validation on all or subset of test cases
        """
        print("\n" + "="*70)
        print("🚀 STARTING VALIDATION RUN")
        print("="*70)
        
        test_cases = self.test_cases[:limit] if limit else self.test_cases
        print(f"Running {len(test_cases)} test cases...\n")
        
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{'='*70}")
            print(f"Progress: {i}/{len(test_cases)}")
            print(f"{'='*70}")
            
            result = self.run_single_test(test_case)
            results.append(result)
            
            # Brief pause between tests
            time.sleep(1)
        
        self.results = results
        return results
    
    def compute_summary_statistics(self) -> Dict:
        """
        Compute aggregate statistics across all test cases
        """
        if not self.results:
            return {}
        
        # Success rate
        successful = [r for r in self.results if r['status'] == 'success']
        success_rate = len(successful) / len(self.results)
        
        if not successful:
            return {
                'success_rate': success_rate,
                'total_tests': len(self.results),
                'successful_tests': 0,
                'failed_tests': len(self.results)
            }
        
        # Metric averages
        metrics_to_average = [
            'overall_score',
            'execution_time',
            'agent_confidence'
        ]
        
        summary = {
            'success_rate': success_rate,
            'total_tests': len(self.results),
            'successful_tests': len(successful),
            'failed_tests': len(self.results) - len(successful)
        }
        
        # Compute averages for each metric
        for metric in metrics_to_average:
            values = [r[metric] for r in successful if metric in r]
            if values:
                summary[f'avg_{metric}'] = np.mean(values)
                summary[f'min_{metric}'] = np.min(values)
                summary[f'max_{metric}'] = np.max(values)
                summary[f'std_{metric}'] = np.std(values)
        
        # Detailed metric breakdowns
        groundedness_scores = [r['groundedness']['score'] for r in successful if 'groundedness' in r]
        citation_f1_scores = [r['citation'].get('f1_score', 0) for r in successful if 'citation' in r]
        citation_precision_scores = [r['citation'].get('precision', 0) for r in successful if 'citation' in r]
        citation_recall_scores = [r['citation'].get('recall', 0) for r in successful if 'citation' in r]
        relevancy_scores = [r['answer_relevancy']['score'] for r in successful if 'answer_relevancy' in r]
        retrieval_hits = [r['retrieval_hit'] for r in successful if 'retrieval_hit' in r]
        
        if groundedness_scores:
            summary['avg_groundedness'] = np.mean(groundedness_scores)
            summary['min_groundedness'] = np.min(groundedness_scores)
        
        if citation_f1_scores:
            summary['avg_citation_f1'] = np.mean(citation_f1_scores)
            summary['avg_citation_precision'] = np.mean(citation_precision_scores)
            summary['avg_citation_recall'] = np.mean(citation_recall_scores)
        
        if relevancy_scores:
            summary['avg_relevancy'] = np.mean(relevancy_scores)
            
        if retrieval_hits:
            summary['retrieval_recall'] = np.mean(retrieval_hits)
        
        return summary
    
    def check_acceptance_criteria(self, summary: Dict) -> Dict:
        """
        Check if system meets acceptance criteria from project scope
        """
        criteria = {
            'turnaround_time': {
                'threshold': 300,  # 5 minutes = 300 seconds
                'actual': summary.get('avg_execution_time', 999),
                'passed': summary.get('avg_execution_time', 999) < 300
            },
            'hallucination_rate': {
                'threshold': 0.05,  # <5% hallucination = >95% groundedness
                'actual': 1 - summary.get('avg_groundedness', 0),
                'passed': summary.get('avg_groundedness', 0) >= 0.95
            },
            'quality_score': {
                'threshold': 0.80,  # >80% quality
                'actual': summary.get('avg_overall_score', 0),
                'passed': summary.get('avg_overall_score', 0) >= 0.80
            },
            'success_rate': {
                'threshold': 0.90,  # 90% of tests should pass
                'actual': summary.get('success_rate', 0),
                'passed': summary.get('success_rate', 0) >= 0.90
            }
        }
        
        all_passed = all(c['passed'] for c in criteria.values())
        
        return {
            'all_criteria_met': all_passed,
            'criteria': criteria,
            'summary': summary,
            'detailed_results': self.results
        }
    
    def save_results(self, filepath: str = None):
        """Save results to JSON file"""
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"src/model_validation/reports/results_{timestamp}.json"
        
        summary = self.compute_summary_statistics()
        acceptance = self.check_acceptance_criteria(summary)
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'summary': summary,
            'acceptance_criteria': acceptance,
            'detailed_results': self.results
        }
        
        # Fix: 'acceptance_criteria' key might be duplicated or boolean in original code
        # Ensure we keep the dictionary version
        if isinstance(output.get('acceptance_criteria'), bool):
            output.pop('acceptance_criteria')
        
        with open(filepath, 'w') as f:
            # CHANGED: Added cls=NumpyEncoder to handle numpy types
            json.dump(output, f, indent=2, cls=NumpyEncoder)
        
        print(f"\n💾 Results saved to {filepath}")
        return filepath

def main():
    """Main entry point for validation"""
    
    # Initialize pipeline
    pipeline = ValidationPipeline()
    
    # Run validation (use limit for quick testing)
    # Set limit=None to run all tests
    results = pipeline.run_all_tests(limit=3)  # Start with 3 for quick test
    
    # Compute summary
    summary = pipeline.compute_summary_statistics()
    acceptance = pipeline.check_acceptance_criteria(summary)
    
    # Generate report
    print("\n" + "="*70)
    print("📊 VALIDATION SUMMARY")
    print("="*70)
    
    print(f"\n✅ Success Rate: {summary['success_rate']:.1%}")
    print(f"📈 Average Overall Score: {summary.get('avg_overall_score', 0):.2%}")
    print(f"⏱️  Average Execution Time: {summary.get('avg_execution_time', 0):.2f}s")
    
    print("\n🔍 RETRIEVAL METRICS")
    print(f"   Retrieval Recall (Recall@k): {summary.get('retrieval_recall', 0):.2%}")
    
    print("\n🧠 GENERATION METRICS")
    print(f"   Groundedness: {summary.get('avg_groundedness', 0):.2%}")
    print(f"   Answer Relevancy: {summary.get('avg_relevancy', 0):.2%}")
    print(f"   Citation Precision: {summary.get('avg_citation_precision', 0):.2%}")
    print(f"   Citation Recall: {summary.get('avg_citation_recall', 0):.2%}")
    print(f"   Citation F1: {summary.get('avg_citation_f1', 0):.2%}")
    
    print("\n" + "="*70)
    print("🎯 ACCEPTANCE CRITERIA")
    print("="*70)
    
    for criterion_name, criterion in acceptance['criteria'].items():
        status = "✅" if criterion['passed'] else "❌"
        print(f"{status} {criterion_name}:")
        print(f"   Threshold: {criterion['threshold']}")
        print(f"   Actual: {criterion['actual']:.4f}")
    
    print("\n" + acceptance['summary'])
    
    # Save results
    results_file = pipeline.save_results()
    
    # Exit code for CI/CD
    exit_code = 0 if acceptance['all_criteria_met'] else 1
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)