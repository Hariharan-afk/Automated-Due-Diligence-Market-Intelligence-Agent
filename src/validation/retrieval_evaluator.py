# src/validation/retrieval_evaluator.py
"""
Retrieval Quality Evaluation for RAG Systems

Implements standard Information Retrieval metrics:
- Precision@K, Recall@K
- Mean Reciprocal Rank (MRR)
- Normalized Discounted Cumulative Gain (nDCG@K)
- Mean Average Precision (MAP)
"""

import json
import numpy as np
from typing import List, Dict, Any, Set
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.researcher_agent import ResearcherAgent, SearchResult
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class RetrievalEvaluator:
    """
    Evaluate retrieval quality using ground truth dataset
    
    Ground truth format:
    {
        "query": "What are Apple's main revenue sources?",
        "relevant_chunks": ["chunk_id_1", "chunk_id_2", ...],
        "ticker": "AAPL",
        "category": "revenue"
    }
    """
    
    def __init__(self, ground_truth_file: str):
        """
        Initialize evaluator with ground truth
        
        Args:
            ground_truth_file: Path to JSON file with query-document pairs
        """
        self.ground_truth_file = Path(ground_truth_file)
        self.ground_truth = self._load_ground_truth()
        
        logger.info(f"✓ Loaded {len(self.ground_truth)} ground truth queries")
    
    def _load_ground_truth(self) -> List[Dict]:
        """Load ground truth from JSON file"""
        if not self.ground_truth_file.exists():
            raise FileNotFoundError(
                f"Ground truth file not found: {self.ground_truth_file}\n"
                f"Create it using: python scripts/validation/create_ground_truth.py"
            )
        
        with open(self.ground_truth_file, 'r') as f:
            data = json.load(f)
        
        return data.get('queries', [])
    
    def precision_at_k(
        self,
        retrieved: List[str],
        relevant: Set[str],
        k: int
    ) -> float:
        """
        Precision@K = (# relevant in top-K) / K
        
        Args:
            retrieved: List of retrieved chunk IDs (ranked)
            relevant: Set of relevant chunk IDs
            k: Cutoff position
        
        Returns:
            Precision score (0-1)
        """
        if k == 0:
            return 0.0
        
        top_k = retrieved[:k]
        relevant_in_top_k = sum(1 for cid in top_k if cid in relevant)
        
        return relevant_in_top_k / k
    
    def recall_at_k(
        self,
        retrieved: List[str],
        relevant: Set[str],
        k: int
    ) -> float:
        """
        Recall@K = (# relevant in top-K) / (total # relevant)
        
        Args:
            retrieved: List of retrieved chunk IDs
            relevant: Set of relevant chunk IDs
            k: Cutoff position
        
        Returns:
            Recall score (0-1)
        """
        if len(relevant) == 0:
            return 0.0
        
        top_k = retrieved[:k]
        relevant_in_top_k = sum(1 for cid in top_k if cid in relevant)
        
        return relevant_in_top_k / len(relevant)
    
    def reciprocal_rank(
        self,
        retrieved: List[str],
        relevant: Set[str]
    ) -> float:
        """
        Reciprocal Rank = 1 / (rank of first relevant document)
        
        Args:
            retrieved: List of retrieved chunk IDs (ranked)
            relevant: Set of relevant chunk IDs
        
        Returns:
            RR score (0-1)
        """
        for rank, chunk_id in enumerate(retrieved, start=1):
            if chunk_id in relevant:
                return 1.0 / rank
        
        return 0.0
    
    def dcg_at_k(
        self,
        retrieved: List[str],
        relevant: Set[str],
        k: int
    ) -> float:
        """
        Discounted Cumulative Gain@K
        
        DCG = Σ(rel_i / log2(i+1)) for i in 1..k
        
        Where rel_i = 1 if document is relevant, 0 otherwise
        """
        dcg = 0.0
        
        for i, chunk_id in enumerate(retrieved[:k], start=1):
            relevance = 1.0 if chunk_id in relevant else 0.0
            dcg += relevance / np.log2(i + 1)
        
        return dcg
    
    def ndcg_at_k(
        self,
        retrieved: List[str],
        relevant: Set[str],
        k: int
    ) -> float:
        """
        Normalized DCG@K = DCG@K / IDCG@K
        
        Where IDCG = ideal DCG (all relevant docs at top)
        """
        dcg = self.dcg_at_k(retrieved, relevant, k)
        
        # Ideal DCG: all relevant docs ranked first
        ideal_retrieved = list(relevant) + ['dummy'] * k
        idcg = self.dcg_at_k(ideal_retrieved, relevant, k)
        
        if idcg == 0:
            return 0.0
        
        return dcg / idcg
    
    def average_precision(
        self,
        retrieved: List[str],
        relevant: Set[str]
    ) -> float:
        """
        Average Precision = mean of precision values at each relevant position
        
        Args:
            retrieved: Retrieved chunk IDs
            relevant: Relevant chunk IDs
        
        Returns:
            AP score (0-1)
        """
        if len(relevant) == 0:
            return 0.0
        
        precisions = []
        num_relevant_seen = 0
        
        for i, chunk_id in enumerate(retrieved, start=1):
            if chunk_id in relevant:
                num_relevant_seen += 1
                precision_at_i = num_relevant_seen / i
                precisions.append(precision_at_i)
        
        if not precisions:
            return 0.0
        
        return np.mean(precisions)
    
    def evaluate_single_query(
        self,
        agent: ResearcherAgent,
        query_data: Dict[str, Any],
        k_values: List[int] = [1, 3, 5, 10]
    ) -> Dict[str, float]:
        """
        Evaluate retrieval for a single query
        
        Args:
            agent: ResearcherAgent instance
            query_data: Ground truth query data
            k_values: K values to compute metrics for
        
        Returns:
            Dictionary of metrics
        """
        query = query_data['query']
        relevant_chunks = set(query_data['relevant_chunks'])
        ticker = query_data.get('ticker')
        
        # Retrieve results
        results = agent.search(
            query=query,
            ticker=ticker,
            top_k=max(k_values),
            verbose=False
        )
        
        # Extract chunk IDs
        retrieved_ids = [r.chunk_id for r in results]
        
        # Compute metrics
        metrics = {}
        
        # Precision, Recall, nDCG at different K values
        for k in k_values:
            metrics[f'precision@{k}'] = self.precision_at_k(retrieved_ids, relevant_chunks, k)
            metrics[f'recall@{k}'] = self.recall_at_k(retrieved_ids, relevant_chunks, k)
            metrics[f'ndcg@{k}'] = self.ndcg_at_k(retrieved_ids, relevant_chunks, k)
        
        # MRR and MAP (computed once)
        metrics['mrr'] = self.reciprocal_rank(retrieved_ids, relevant_chunks)
        metrics['map'] = self.average_precision(retrieved_ids, relevant_chunks)
        
        return metrics
    
    def evaluate_all(
        self,
        agent: ResearcherAgent,
        k_values: List[int] = [1, 3, 5, 10]
    ) -> Dict[str, Any]:
        """
        Evaluate on entire ground truth dataset
        
        Args:
            agent: ResearcherAgent instance
            k_values: K values for metrics
        
        Returns:
            {
                'overall': {averaged metrics},
                'per_query': [individual results],
                'by_category': {category-wise breakdown}
            }
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 STARTING RETRIEVAL EVALUATION")
        logger.info(f"{'='*80}\n")
        logger.info(f"Ground truth queries: {len(self.ground_truth)}")
        logger.info(f"K values: {k_values}\n")
        
        per_query_results = []
        all_metrics = {f'precision@{k}': [] for k in k_values}
        all_metrics.update({f'recall@{k}': [] for k in k_values})
        all_metrics.update({f'ndcg@{k}': [] for k in k_values})
        all_metrics['mrr'] = []
        all_metrics['map'] = []
        
        # Evaluate each query
        for i, query_data in enumerate(self.ground_truth, 1):
            query = query_data['query']
            logger.info(f"[{i}/{len(self.ground_truth)}] Evaluating: {query[:60]}...")
            
            metrics = self.evaluate_single_query(agent, query_data, k_values)
            
            # Store per-query results
            per_query_results.append({
                'query': query,
                'ticker': query_data.get('ticker'),
                'category': query_data.get('category'),
                'metrics': metrics
            })
            
            # Aggregate metrics
            for metric_name, value in metrics.items():
                all_metrics[metric_name].append(value)
        
        # Compute averages
        overall_metrics = {
            metric_name: np.mean(values)
            for metric_name, values in all_metrics.items()
        }
        
        # Breakdown by category
        by_category = self._compute_category_breakdown(per_query_results)
        
        # Print summary
        self._print_evaluation_summary(overall_metrics, by_category)
        
        return {
            'overall': overall_metrics,
            'per_query': per_query_results,
            'by_category': by_category,
            'metadata': {
                'num_queries': len(self.ground_truth),
                'alpha': agent.alpha,
                'embedding_model': str(agent.embedding_model),
                'k_values': k_values,
                'timestamp': datetime.now().isoformat()
            }
        }
    
    def _compute_category_breakdown(
        self,
        per_query_results: List[Dict]
    ) -> Dict[str, Dict[str, float]]:
        """Compute metrics grouped by query category"""
        categories = {}
        
        for result in per_query_results:
            category = result.get('category', 'general')
            
            if category not in categories:
                categories[category] = {metric: [] for metric in result['metrics'].keys()}
            
            for metric_name, value in result['metrics'].items():
                categories[category][metric_name].append(value)
        
        # Average per category
        category_averages = {}
        for category, metrics_lists in categories.items():
            category_averages[category] = {
                metric: np.mean(values)
                for metric, values in metrics_lists.items()
            }
        
        return category_averages
    
    def _print_evaluation_summary(
        self,
        overall: Dict[str, float],
        by_category: Dict[str, Dict[str, float]]
    ):
        """Pretty print evaluation results"""
        print(f"\n{'='*80}")
        print(f"📊 EVALUATION RESULTS")
        print(f"{'='*80}\n")
        
        print("Overall Metrics:")
        print("-" * 80)
        
        # Group by metric type
        for k in [1, 3, 5, 10]:
            if f'precision@{k}' in overall:
                print(f"  @{k:2d}: Precision={overall[f'precision@{k}']:.3f}  "
                      f"Recall={overall[f'recall@{k}']:.3f}  "
                      f"nDCG={overall[f'ndcg@{k}']:.3f}")
        
        print(f"\n  MRR: {overall.get('mrr', 0):.3f}")
        print(f"  MAP: {overall.get('map', 0):.3f}")
        
        # Category breakdown
        if by_category:
            print(f"\n\nBreakdown by Category:")
            print("-" * 80)
            
            for category, metrics in by_category.items():
                print(f"\n  {category.upper()}:")
                print(f"    Precision@5: {metrics.get('precision@5', 0):.3f}")
                print(f"    Recall@5: {metrics.get('recall@5', 0):.3f}")
                print(f"    nDCG@5: {metrics.get('ndcg@5', 0):.3f}")
        
        print(f"\n{'='*80}\n")
    
    def save_results(
        self,
        results: Dict[str, Any],
        output_file: str
    ):
        """Save evaluation results to JSON"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"✓ Results saved to {output_path}")
    
    def generate_html_report(
        self,
        results: Dict[str, Any],
        output_file: str
    ):
        """Generate HTML report with visualizations"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Retrieval Evaluation Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #3498db; color: white; }}
        tr:hover {{ background: #f5f5f5; }}
        .metric {{ font-weight: bold; color: #2980b9; }}
        .good {{ color: #27ae60; }}
        .warning {{ color: #f39c12; }}
        .poor {{ color: #e74c3c; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Retrieval Evaluation Report</h1>
        
        <p><strong>Date:</strong> {results['metadata'].get('timestamp', 'N/A')}</p>
        <p><strong>Queries Evaluated:</strong> {results['metadata']['num_queries']}</p>
        <p><strong>Alpha (Hybrid Weight):</strong> {results['metadata']['alpha']}</p>
        
        <h2>Overall Performance</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>@1</th>
                <th>@3</th>
                <th>@5</th>
                <th>@10</th>
            </tr>
            <tr>
                <td class="metric">Precision</td>
                <td class="{self._get_color_class(results['overall'].get('precision@1', 0))}">{results['overall'].get('precision@1', 0):.3f}</td>
                <td class="{self._get_color_class(results['overall'].get('precision@3', 0))}">{results['overall'].get('precision@3', 0):.3f}</td>
                <td class="{self._get_color_class(results['overall'].get('precision@5', 0))}">{results['overall'].get('precision@5', 0):.3f}</td>
                <td class="{self._get_color_class(results['overall'].get('precision@10', 0))}">{results['overall'].get('precision@10', 0):.3f}</td>
            </tr>
            <tr>
                <td class="metric">Recall</td>
                <td class="{self._get_color_class(results['overall'].get('recall@1', 0))}">{results['overall'].get('recall@1', 0):.3f}</td>
                <td class="{self._get_color_class(results['overall'].get('recall@3', 0))}">{results['overall'].get('recall@3', 0):.3f}</td>
                <td class="{self._get_color_class(results['overall'].get('recall@5', 0))}">{results['overall'].get('recall@5', 0):.3f}</td>
                <td class="{self._get_color_class(results['overall'].get('recall@10', 0))}">{results['overall'].get('recall@10', 0):.3f}</td>
            </tr>
            <tr>
                <td class="metric">nDCG</td>
                <td class="{self._get_color_class(results['overall'].get('ndcg@1', 0))}">{results['overall'].get('ndcg@1', 0):.3f}</td>
                <td class="{self._get_color_class(results['overall'].get('ndcg@3', 0))}">{results['overall'].get('ndcg@3', 0):.3f}</td>
                <td class="{self._get_color_class(results['overall'].get('ndcg@5', 0))}">{results['overall'].get('ndcg@5', 0):.3f}</td>
                <td class="{self._get_color_class(results['overall'].get('ndcg@10', 0))}">{results['overall'].get('ndcg@10', 0):.3f}</td>
            </tr>
        </table>
        
        <table>
            <tr>
                <th>Metric</th>
                <th>Score</th>
            </tr>
            <tr>
                <td class="metric">Mean Reciprocal Rank (MRR)</td>
                <td class="{self._get_color_class(results['overall'].get('mrr', 0))}">{results['overall'].get('mrr', 0):.3f}</td>
            </tr>
            <tr>
                <td class="metric">Mean Average Precision (MAP)</td>
                <td class="{self._get_color_class(results['overall'].get('map', 0))}">{results['overall'].get('map', 0):.3f}</td>
            </tr>
        </table>
        
        <h2>Performance by Category</h2>
        <table>
            <tr>
                <th>Category</th>
                <th>Precision@5</th>
                <th>Recall@5</th>
                <th>nDCG@5</th>
            </tr>
"""
        
        for category, metrics in results.get('by_category', {}).items():
            html += f"""
            <tr>
                <td>{category}</td>
                <td class="{self._get_color_class(metrics.get('precision@5', 0))}">{metrics.get('precision@5', 0):.3f}</td>
                <td class="{self._get_color_class(metrics.get('recall@5', 0))}">{metrics.get('recall@5', 0):.3f}</td>
                <td class="{self._get_color_class(metrics.get('ndcg@5', 0))}">{metrics.get('ndcg@5', 0):.3f}</td>
            </tr>
"""
        
        html += """
        </table>
    </div>
</body>
</html>
"""
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        logger.info(f"✓ HTML report saved to {output_path}")
    
    def _get_color_class(self, score: float) -> str:
        """Get CSS class based on score threshold"""
        if score >= 0.7:
            return 'good'
        elif score >= 0.5:
            return 'warning'
        else:
            return 'poor'


# ==================== STANDALONE TESTING ====================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("TESTING RETRIEVAL EVALUATOR")
    print("="*80 + "\n")
    
    # Initialize agent
    from src.agents.researcher_agent import ResearcherAgent
    
    agent = ResearcherAgent(
        qdrant_host='localhost',
        alpha=0.5,
        top_k=10
    )
    
    # Load corpus
    print("Loading corpus...")
    agent.load_corpus()
    
    # Initialize evaluator
    evaluator = RetrievalEvaluator(
        ground_truth_file='data/validation/ground_truth.json'
    )
    
    # Run evaluation
    results = evaluator.evaluate_all(agent, k_values=[1, 3, 5, 10])
    
    # Save results
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    evaluator.save_results(
        results,
        f'results/validation/retrieval_eval_{timestamp}.json'
    )
    
    evaluator.generate_html_report(
        results,
        f'results/validation/retrieval_eval_{timestamp}.html'
    )
    
    print("\n✅ Evaluation complete!")
    print(f"📄 View HTML report: results/validation/retrieval_eval_{timestamp}.html")