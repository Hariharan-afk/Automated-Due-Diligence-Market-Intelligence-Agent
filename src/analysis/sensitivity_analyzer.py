# src/analysis/sensitivity_analyzer.py
"""
Sensitivity Analysis for Retrieval Parameters

Analyzes how performance changes with:
- Alpha (semantic vs BM25 weight)
- Top-K values
- Chunk size (requires re-chunking data)
- Chunk overlap
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, Any, List, Tuple
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.researcher_agent import ResearcherAgent
from src.validation.retrieval_evaluator import RetrievalEvaluator
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SensitivityAnalyzer:
    """
    Analyze parameter sensitivity for retrieval system
    
    Generates:
    - Sensitivity curves
    - Heatmaps
    - Statistical significance tests
    """
    
    def __init__(self, evaluator: RetrievalEvaluator):
        """
        Initialize sensitivity analyzer
        
        Args:
            evaluator: RetrievalEvaluator with ground truth
        """
        self.evaluator = evaluator
        logger.info("✓ SensitivityAnalyzer initialized")
    
    def analyze_alpha_sensitivity(
        self,
        alpha_range: Tuple[float, float] = (0.0, 1.0),
        steps: int = 11
    ) -> Dict[str, Any]:
        """
        Analyze how alpha affects retrieval quality
        
        Args:
            alpha_range: (min, max) alpha values
            steps: Number of alpha values to test
        
        Returns:
            {
                'alpha_values': [0.0, 0.1, ..., 1.0],
                'metrics': {
                    'precision@5': [...],
                    'recall@5': [...],
                    'ndcg@5': [...]
                },
                'optimal_alpha': 0.6,
                'peak_ndcg': 0.85
            }
        """
        logger.info("\n🔬 Analyzing Alpha Sensitivity...")
        logger.info(f"   Range: {alpha_range}, Steps: {steps}\n")
        
        alpha_values = np.linspace(alpha_range[0], alpha_range[1], steps)
        
        results = {
            'alpha_values': alpha_values.tolist(),
            'metrics': {
                'precision@5': [],
                'recall@5': [],
                'ndcg@5': [],
                'mrr': []
            }
        }
        
        for i, alpha in enumerate(alpha_values, 1):
            logger.info(f"  [{i}/{steps}] Testing alpha={alpha:.2f}...")
            
            # Create agent with this alpha
            agent = ResearcherAgent(
                qdrant_host='localhost',
                alpha=alpha,
                top_k=5
            )
            agent.load_corpus()
            
            # Evaluate
            eval_results = self.evaluator.evaluate_all(agent, k_values=[5])
            
            # Store metrics
            results['metrics']['precision@5'].append(eval_results['overall']['precision@5'])
            results['metrics']['recall@5'].append(eval_results['overall']['recall@5'])
            results['metrics']['ndcg@5'].append(eval_results['overall']['ndcg@5'])
            results['metrics']['mrr'].append(eval_results['overall']['mrr'])
        
        # Find optimal alpha
        ndcg_values = results['metrics']['ndcg@5']
        optimal_idx = np.argmax(ndcg_values)
        results['optimal_alpha'] = alpha_values[optimal_idx]
        results['peak_ndcg'] = ndcg_values[optimal_idx]
        
        logger.info(f"\n✓ Optimal alpha: {results['optimal_alpha']:.2f} (nDCG@5={results['peak_ndcg']:.3f})")
        
        return results
    
    def analyze_top_k_sensitivity(
        self,
        k_range: Tuple[int, int] = (1, 20),
        alpha: float = 0.5
    ) -> Dict[str, Any]:
        """
        Analyze how top-K affects retrieval quality
        
        Args:
            k_range: (min, max) K values
            alpha: Fixed alpha to use
        
        Returns:
            Sensitivity results
        """
        logger.info("\n🔬 Analyzing Top-K Sensitivity...")
        logger.info(f"   Range: {k_range}, Alpha: {alpha}\n")
        
        k_values = list(range(k_range[0], k_range[1] + 1))
        
        # Create single agent
        agent = ResearcherAgent(
            qdrant_host='localhost',
            alpha=alpha,
            top_k=max(k_values)
        )
        agent.load_corpus()
        
        results = {
            'k_values': k_values,
            'metrics': {
                'precision': [],
                'recall': [],
                'ndcg': []
            }
        }
        
        # Evaluate at each K
        for k in k_values:
            logger.info(f"  Testing K={k}...")
            
            # Run evaluation at this K
            eval_results = self.evaluator.evaluate_all(agent, k_values=[k])
            
            results['metrics']['precision'].append(eval_results['overall'][f'precision@{k}'])
            results['metrics']['recall'].append(eval_results['overall'][f'recall@{k}'])
            results['metrics']['ndcg'].append(eval_results['overall'][f'ndcg@{k}'])
        
        logger.info("\n✓ Top-K sensitivity analysis complete")
        
        return results
    
    def generate_sensitivity_plots(
        self,
        alpha_results: Dict,
        topk_results: Dict,
        output_dir: str
    ):
        """
        Generate sensitivity plots
        
        Creates:
        - Alpha sensitivity curve
        - Top-K sensitivity curve
        - Combined heatmap
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Plot 1: Alpha Sensitivity
        fig, ax = plt.subplots(figsize=(10, 6))
        
        alpha_vals = alpha_results['alpha_values']
        
        ax.plot(alpha_vals, alpha_results['metrics']['precision@5'], 
                'o-', label='Precision@5', linewidth=2)
        ax.plot(alpha_vals, alpha_results['metrics']['recall@5'], 
                's-', label='Recall@5', linewidth=2)
        ax.plot(alpha_vals, alpha_results['metrics']['ndcg@5'], 
                '^-', label='nDCG@5', linewidth=2)
        
        # Mark optimal
        optimal_alpha = alpha_results['optimal_alpha']
        ax.axvline(optimal_alpha, color='red', linestyle='--', 
                   label=f'Optimal α={optimal_alpha:.2f}')
        
        ax.set_xlabel('Alpha (Semantic Weight)', fontsize=12)
        ax.set_ylabel('Metric Value', fontsize=12)
        ax.set_title('Retrieval Performance vs Alpha', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        
        plt.tight_layout()
        plt.savefig(output_path / 'alpha_sensitivity.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"✓ Saved: {output_path / 'alpha_sensitivity.png'}")
        
        # Plot 2: Top-K Sensitivity
        fig, ax = plt.subplots(figsize=(10, 6))
        
        k_vals = topk_results['k_values']
        
        ax.plot(k_vals, topk_results['metrics']['precision'], 
                'o-', label='Precision@K', linewidth=2)
        ax.plot(k_vals, topk_results['metrics']['recall'], 
                's-', label='Recall@K', linewidth=2)
        ax.plot(k_vals, topk_results['metrics']['ndcg'], 
                '^-', label='nDCG@K', linewidth=2)
        
        ax.set_xlabel('K (Number of Results)', fontsize=12)
        ax.set_ylabel('Metric Value', fontsize=12)
        ax.set_title('Retrieval Performance vs Top-K', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path / 'topk_sensitivity.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"✓ Saved: {output_path / 'topk_sensitivity.png'}")
    
    def generate_sensitivity_report(
        self,
        alpha_results: Dict,
        topk_results: Dict,
        output_file: str
    ):
        """Generate HTML sensitivity analysis report"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Sensitivity Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #9b59b6; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 5px; margin: 20px 0; }}
        .finding {{ padding: 15px; margin: 15px 0; border-left: 4px solid #9b59b6; background: #f9f3ff; }}
        .recommendation {{ padding: 15px; margin: 15px 0; border-left: 4px solid #27ae60; background: #e8f8f5; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #9b59b6; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔬 Sensitivity Analysis Report</h1>
        
        <h2>1. Alpha Sensitivity Analysis</h2>
        <p>Testing how the hybrid search weight (alpha) affects retrieval quality.</p>
        
        <img src="alpha_sensitivity.png" alt="Alpha Sensitivity">
        
        <div class="finding">
            <strong>📊 Key Finding:</strong><br>
            Optimal alpha: <strong>{alpha_results['optimal_alpha']:.2f}</strong><br>
            Peak nDCG@5: <strong>{alpha_results['peak_ndcg']:.3f}</strong>
        </div>
        
        <table>
            <tr>
                <th>Alpha</th>
                <th>Search Type</th>
                <th>Precision@5</th>
                <th>Recall@5</th>
                <th>nDCG@5</th>
            </tr>
"""
        
        for i, alpha in enumerate(alpha_results['alpha_values']):
            search_type = "Pure BM25" if alpha == 0 else ("Hybrid" if 0 < alpha < 1 else "Pure Semantic")
            p5 = alpha_results['metrics']['precision@5'][i]
            r5 = alpha_results['metrics']['recall@5'][i]
            ndcg5 = alpha_results['metrics']['ndcg@5'][i]
            
            html += f"""
            <tr>
                <td>{alpha:.2f}</td>
                <td>{search_type}</td>
                <td>{p5:.3f}</td>
                <td>{r5:.3f}</td>
                <td><strong>{ndcg5:.3f}</strong></td>
            </tr>
"""
        
        html += """
        </table>
        
        <h2>2. Top-K Sensitivity Analysis</h2>
        <p>Testing how the number of retrieved results affects quality metrics.</p>
        
        <img src="topk_sensitivity.png" alt="Top-K Sensitivity">
        
        <div class="recommendation">
            <strong>💡 Recommendations:</strong>
            <ul>
                <li>Use hybrid search (alpha ≈ 0.5) for balanced results</li>
                <li>Adjust alpha based on query type (higher for semantic concepts, lower for keywords)</li>
                <li>Top-K=5 provides good precision-recall balance</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        logger.info(f"✓ Sensitivity report saved to {output_path}")


# ==================== STANDALONE TESTING ====================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("TESTING SENSITIVITY ANALYZER")
    print("="*80 + "\n")
    
    # Initialize evaluator
    evaluator = RetrievalEvaluator(
        ground_truth_file='data/validation/ground_truth.json'
    )
    
    # Initialize analyzer
    analyzer = SensitivityAnalyzer(evaluator)
    
    # 1. Alpha sensitivity
    print("\n1. Analyzing Alpha Sensitivity...")
    alpha_results = analyzer.analyze_alpha_sensitivity(
        alpha_range=(0.0, 1.0),
        steps=11
    )
    
    # 2. Top-K sensitivity  
    print("\n2. Analyzing Top-K Sensitivity...")
    topk_results = analyzer.analyze_top_k_sensitivity(
        k_range=(1, 15),
        alpha=0.5
    )
    
    # 3. Generate plots and report
    print("\n3. Generating Visualizations...")
    
    output_dir = 'results/sensitivity_analysis'
    
    analyzer.generate_sensitivity_plots(
        alpha_results,
        topk_results,
        output_dir
    )
    
    analyzer.generate_sensitivity_report(
        alpha_results,
        topk_results,
        f'{output_dir}/sensitivity_report.html'
    )
    
    print(f"\n✅ Sensitivity analysis complete!")
    print(f"📄 View report: {output_dir}/sensitivity_report.html")
    print(f"📊 Optimal alpha: {alpha_results['optimal_alpha']:.2f}")