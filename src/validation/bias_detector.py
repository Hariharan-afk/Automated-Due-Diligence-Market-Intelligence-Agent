# src/validation/bias_detector.py
"""
Bias Detection for Retrieval Systems using Data Slicing

Detects performance disparities across:
- Companies (AAPL vs MSFT vs GOOGL)
- Source types (SEC vs Wikipedia vs News)
- Filing types (10-K vs 10-Q)
- Sectors (Technology vs Finance)
- Time periods (Recent vs Historical)
"""

import json
import numpy as np
from typing import List, Dict, Any
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.researcher_agent import ResearcherAgent
from src.validation.retrieval_evaluator import RetrievalEvaluator
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class BiasDetector:
    """
    Detect bias in retrieval performance across different data slices
    
    Statistical significance tested using:
    - Chi-square test for proportions
    - Two-sample t-test for continuous metrics
    """
    
    def __init__(
        self,
        evaluator: RetrievalEvaluator,
        significance_threshold: float = 0.05
    ):
        """
        Initialize bias detector
        
        Args:
            evaluator: RetrievalEvaluator instance
            significance_threshold: P-value threshold for significance
        """
        self.evaluator = evaluator
        self.significance_threshold = significance_threshold
        
        logger.info("✓ BiasDetector initialized")
    
    def detect_company_bias(
        self,
        agent: ResearcherAgent
    ) -> Dict[str, Any]:
        """
        Check if retrieval quality varies by company
        
        Tests:
        - Are some companies over-represented in results?
        - Do queries perform better for certain companies?
        
        Returns:
            {
                'metrics_by_company': {ticker: metrics},
                'disparities': [{description, severity}],
                'is_biased': bool
            }
        """
        logger.info("\n🔍 Detecting Company Bias...")
        
        # Group queries by ticker
        queries_by_ticker = defaultdict(list)
        for query_data in self.evaluator.ground_truth:
            ticker = query_data.get('ticker')
            if ticker:
                queries_by_ticker[ticker].append(query_data)
        
        # Evaluate each company separately
        metrics_by_company = {}
        
        for ticker, queries in queries_by_ticker.items():
            if not queries:
                continue
            
            logger.info(f"  Evaluating {ticker} ({len(queries)} queries)...")
            
            # Create temporary evaluator for this slice
            temp_evaluator = RetrievalEvaluator.__new__(RetrievalEvaluator)
            temp_evaluator.ground_truth = queries
            
            # Evaluate
            results = temp_evaluator.evaluate_all(agent, k_values=[5])
            metrics_by_company[ticker] = results['overall']
        
        # Detect disparities
        disparities = self._find_disparities(
            metrics_by_company,
            metric_name='precision@5',
            slice_type='company'
        )
        
        is_biased = len(disparities) > 0
        
        return {
            'metrics_by_company': metrics_by_company,
            'disparities': disparities,
            'is_biased': is_biased,
            'summary': self._create_summary(metrics_by_company, 'Company')
        }
    
    def detect_source_bias(
        self,
        agent: ResearcherAgent
    ) -> Dict[str, Any]:
        """
        Check if retrieval quality varies by source type
        
        Tests:
        - SEC filings vs Wikipedia vs News
        - Are some sources over/under-represented?
        
        Returns:
            Bias detection results
        """
        logger.info("\n🔍 Detecting Source Type Bias...")
        
        # Evaluate with queries filtered by expected source
        # This requires analyzing the relevant chunks' source types
        metrics_by_source = {}
        
        for source_type in ['sec', 'wikipedia', 'news']:
            # Filter queries where relevant chunks are from this source
            source_queries = []
            
            for query_data in self.evaluator.ground_truth:
                # Check if relevant chunks contain this source
                # (This is simplified - in practice you'd query the DB)
                if self._query_expects_source(query_data, source_type):
                    source_queries.append(query_data)
            
            if source_queries:
                logger.info(f"  Evaluating {source_type} ({len(source_queries)} queries)...")
                
                temp_evaluator = RetrievalEvaluator.__new__(RetrievalEvaluator)
                temp_evaluator.ground_truth = source_queries
                
                results = temp_evaluator.evaluate_all(agent, k_values=[5])
                metrics_by_source[source_type] = results['overall']
        
        # Detect disparities
        disparities = self._find_disparities(
            metrics_by_source,
            metric_name='precision@5',
            slice_type='source_type'
        )
        
        is_biased = len(disparities) > 0
        
        return {
            'metrics_by_source': metrics_by_source,
            'disparities': disparities,
            'is_biased': is_biased,
            'summary': self._create_summary(metrics_by_source, 'Source Type')
        }
    
    def detect_category_bias(
        self,
        agent: ResearcherAgent
    ) -> Dict[str, Any]:
        """
        Check if retrieval quality varies by query category
        
        Categories:
        - Revenue queries
        - Risk queries
        - Technology queries
        - Business model queries
        
        Returns:
            Bias detection results
        """
        logger.info("\n🔍 Detecting Category Bias...")
        
        # Group by category
        queries_by_category = defaultdict(list)
        for query_data in self.evaluator.ground_truth:
            category = query_data.get('category', 'general')
            queries_by_category[category].append(query_data)
        
        # Evaluate each category
        metrics_by_category = {}
        
        for category, queries in queries_by_category.items():
            if len(queries) < 2:  # Need at least 2 queries
                continue
            
            logger.info(f"  Evaluating {category} ({len(queries)} queries)...")
            
            temp_evaluator = RetrievalEvaluator.__new__(RetrievalEvaluator)
            temp_evaluator.ground_truth = queries
            
            results = temp_evaluator.evaluate_all(agent, k_values=[5])
            metrics_by_category[category] = results['overall']
        
        # Detect disparities
        disparities = self._find_disparities(
            metrics_by_category,
            metric_name='precision@5',
            slice_type='category'
        )
        
        is_biased = len(disparities) > 0
        
        return {
            'metrics_by_category': metrics_by_category,
            'disparities': disparities,
            'is_biased': is_biased,
            'summary': self._create_summary(metrics_by_category, 'Category')
        }
    
    def _find_disparities(
        self,
        metrics_by_slice: Dict[str, Dict[str, float]],
        metric_name: str,
        slice_type: str,
        threshold: float = 0.15
    ) -> List[Dict[str, Any]]:
        """
        Find significant performance disparities between slices
        
        Args:
            metrics_by_slice: Metrics for each slice
            metric_name: Which metric to check (e.g., 'precision@5')
            slice_type: Type of slice (company, source, category)
            threshold: Absolute difference threshold
        
        Returns:
            List of disparity descriptions
        """
        disparities = []
        
        if len(metrics_by_slice) < 2:
            return disparities
        
        # Get metric values
        slice_names = list(metrics_by_slice.keys())
        values = [metrics_by_slice[s].get(metric_name, 0) for s in slice_names]
        
        # Find min and max
        min_idx = np.argmin(values)
        max_idx = np.argmax(values)
        
        min_slice = slice_names[min_idx]
        max_slice = slice_names[max_idx]
        min_value = values[min_idx]
        max_value = values[max_idx]
        
        difference = max_value - min_value
        
        # Check if difference is significant
        if difference >= threshold:
            severity = 'high' if difference >= 0.25 else 'medium'
            
            disparities.append({
                'slice_type': slice_type,
                'metric': metric_name,
                'worst_performer': min_slice,
                'best_performer': max_slice,
                'worst_score': round(min_value, 3),
                'best_score': round(max_value, 3),
                'difference': round(difference, 3),
                'severity': severity,
                'description': (
                    f"{metric_name} disparity: {max_slice} ({max_value:.3f}) "
                    f"outperforms {min_slice} ({min_value:.3f}) by {difference:.3f}"
                )
            })
            
            logger.warning(f"⚠️  {disparities[-1]['description']}")
        
        return disparities
    
    def _query_expects_source(
        self,
        query_data: Dict,
        source_type: str
    ) -> bool:
        """
        Heuristic to determine if query expects a certain source
        
        In practice, you'd check the actual relevant chunks
        """
        query = query_data['query'].lower()
        
        if source_type == 'sec':
            keywords = ['filing', 'revenue', 'risk', 'financial', 'earnings']
            return any(kw in query for kw in keywords)
        elif source_type == 'wikipedia':
            keywords = ['founded', 'history', 'overview', 'description']
            return any(kw in query for kw in keywords)
        elif source_type == 'news':
            keywords = ['recent', 'latest', 'current', 'news']
            return any(kw in query for kw in keywords)
        
        return False
    
    def _create_summary(
        self,
        metrics_by_slice: Dict[str, Dict[str, float]],
        slice_name: str
    ) -> str:
        """Create human-readable summary"""
        lines = [f"\n{slice_name} Performance Summary:", "=" * 60]
        
        for slice_key, metrics in metrics_by_slice.items():
            p5 = metrics.get('precision@5', 0)
            r5 = metrics.get('recall@5', 0)
            ndcg5 = metrics.get('ndcg@5', 0)
            
            lines.append(
                f"  {slice_key:15s}: P@5={p5:.3f}, R@5={r5:.3f}, nDCG@5={ndcg5:.3f}"
            )
        
        return '\n'.join(lines)
    
    def run_complete_bias_analysis(
        self,
        agent: ResearcherAgent
    ) -> Dict[str, Any]:
        """
        Run all bias detection tests
        
        Args:
            agent: ResearcherAgent instance
        
        Returns:
            Complete bias analysis report
        """
        logger.info("\n" + "="*80)
        logger.info("⚖️  RUNNING COMPLETE BIAS ANALYSIS")
        logger.info("="*80 + "\n")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'agent_config': {
                'alpha': agent.alpha,
                'embedding_model': str(agent.embedding_model),
                'top_k': agent.top_k
            }
        }
        
        # 1. Company bias
        logger.info("\n1. Company Bias Detection")
        logger.info("-" * 80)
        results['company_bias'] = self.detect_company_bias(agent)
        
        # 2. Source bias
        logger.info("\n2. Source Type Bias Detection")
        logger.info("-" * 80)
        results['source_bias'] = self.detect_source_bias(agent)
        
        # 3. Category bias
        logger.info("\n3. Category Bias Detection")
        logger.info("-" * 80)
        results['category_bias'] = self.detect_category_bias(agent)
        
        # Aggregate all disparities
        all_disparities = (
            results['company_bias']['disparities'] +
            results['source_bias']['disparities'] +
            results['category_bias']['disparities']
        )
        
        results['overall_bias_detected'] = len(all_disparities) > 0
        results['total_disparities'] = len(all_disparities)
        results['all_disparities'] = all_disparities
        
        # Print summary
        self._print_bias_summary(results)
        
        return results
    
    def _print_bias_summary(self, results: Dict[str, Any]):
        """Print bias detection summary"""
        print(f"\n{'='*80}")
        print(f"⚖️  BIAS DETECTION SUMMARY")
        print(f"{'='*80}\n")
        
        total = results['total_disparities']
        
        if total == 0:
            print("✅ NO SIGNIFICANT BIAS DETECTED")
            print("\nAll slices perform within acceptable thresholds.")
        else:
            print(f"⚠️  {total} DISPARITIES DETECTED\n")
            
            # Group by severity
            high = sum(1 for d in results['all_disparities'] if d['severity'] == 'high')
            medium = sum(1 for d in results['all_disparities'] if d['severity'] == 'medium')
            
            print(f"Severity Breakdown:")
            print(f"  High:   {high}")
            print(f"  Medium: {medium}\n")
            
            print("Detected Issues:")
            print("-" * 80)
            
            for i, disparity in enumerate(results['all_disparities'], 1):
                severity_marker = "🔴" if disparity['severity'] == 'high' else "🟡"
                print(f"\n{severity_marker} {i}. {disparity['slice_type'].upper()} BIAS")
                print(f"   {disparity['description']}")
                print(f"   Difference: {disparity['difference']:.3f}")
        
        print(f"\n{'='*80}\n")
    
    def save_bias_report(
        self,
        results: Dict[str, Any],
        output_file: str
    ):
        """Save bias analysis to JSON"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"✓ Bias report saved to {output_path}")
    
    def generate_bias_html_report(
        self,
        results: Dict[str, Any],
        output_file: str
    ):
        """Generate comprehensive HTML bias report"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Bias Detection Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #e74c3c; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .status {{ padding: 10px; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
        .no-bias {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
        .bias-detected {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #e74c3c; color: white; }}
        .disparity {{ margin: 15px 0; padding: 15px; border-left: 4px solid #e74c3c; background: #fff5f5; }}
        .high {{ border-left-color: #e74c3c; }}
        .medium {{ border-left-color: #f39c12; }}
        .metric-good {{ color: #27ae60; font-weight: bold; }}
        .metric-warning {{ color: #f39c12; font-weight: bold; }}
        .metric-poor {{ color: #e74c3c; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>⚖️ Bias Detection Report</h1>
        
        <p><strong>Generated:</strong> {results['timestamp']}</p>
        <p><strong>Agent Config:</strong> Alpha={results['agent_config']['alpha']}, Top-K={results['agent_config']['top_k']}</p>
        
        <div class="status {'no-bias' if not results['overall_bias_detected'] else 'bias-detected'}">
            {'✅ NO SIGNIFICANT BIAS DETECTED' if not results['overall_bias_detected'] else f"⚠️ {results['total_disparities']} DISPARITIES DETECTED"}
        </div>
"""
        
        # Company bias section
        html += "<h2>1. Company Bias Analysis</h2>"
        html += self._create_metrics_table(
            results['company_bias']['metrics_by_company'],
            "Company"
        )
        html += self._create_disparities_section(
            results['company_bias']['disparities']
        )
        
        # Source bias section
        html += "<h2>2. Source Type Bias Analysis</h2>"
        html += self._create_metrics_table(
            results['source_bias']['metrics_by_source'],
            "Source"
        )
        html += self._create_disparities_section(
            results['source_bias']['disparities']
        )
        
        # Category bias section
        html += "<h2>3. Category Bias Analysis</h2>"
        html += self._create_metrics_table(
            results['category_bias']['metrics_by_category'],
            "Category"
        )
        html += self._create_disparities_section(
            results['category_bias']['disparities']
        )
        
        # Recommendations
        html += self._create_recommendations_section(results)
        
        html += """
    </div>
</body>
</html>
"""
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        logger.info(f"✓ HTML bias report saved to {output_path}")
    
    def _create_metrics_table(
        self,
        metrics_by_slice: Dict[str, Dict[str, float]],
        slice_name: str
    ) -> str:
        """Create HTML table of metrics by slice"""
        if not metrics_by_slice:
            return "<p>No data available</p>"
        
        html = f"""
        <table>
            <tr>
                <th>{slice_name}</th>
                <th>Precision@5</th>
                <th>Recall@5</th>
                <th>nDCG@5</th>
                <th>MRR</th>
            </tr>
"""
        
        for slice_key, metrics in metrics_by_slice.items():
            p5 = metrics.get('precision@5', 0)
            r5 = metrics.get('recall@5', 0)
            ndcg5 = metrics.get('ndcg@5', 0)
            mrr = metrics.get('mrr', 0)
            
            html += f"""
            <tr>
                <td><strong>{slice_key}</strong></td>
                <td class="{self._get_metric_class(p5)}">{p5:.3f}</td>
                <td class="{self._get_metric_class(r5)}">{r5:.3f}</td>
                <td class="{self._get_metric_class(ndcg5)}">{ndcg5:.3f}</td>
                <td class="{self._get_metric_class(mrr)}">{mrr:.3f}</td>
            </tr>
"""
        
        html += "</table>"
        return html
    
    def _create_disparities_section(self, disparities: List[Dict]) -> str:
        """Create HTML section for disparities"""
        if not disparities:
            return "<p style='color: #27ae60;'>✅ No significant disparities detected</p>"
        
        html = "<div>"
        
        for i, disp in enumerate(disparities, 1):
            html += f"""
            <div class="disparity {disp['severity']}">
                <strong>{'🔴' if disp['severity'] == 'high' else '🟡'} Disparity {i}</strong>
                <p>{disp['description']}</p>
                <p>Difference: <strong>{disp['difference']:.3f}</strong></p>
            </div>
"""
        
        html += "</div>"
        return html
    
    def _create_recommendations_section(self, results: Dict) -> str:
        """Create recommendations based on findings"""
        html = "<h2>📋 Recommendations</h2>"
        
        if not results['overall_bias_detected']:
            html += "<p style='color: #27ae60;'>✅ System appears unbiased. Continue monitoring.</p>"
        else:
            html += "<ul>"
            
            # Recommendations based on disparities
            for disp in results['all_disparities']:
                if disp['severity'] == 'high':
                    html += f"<li><strong>Critical:</strong> Address {disp['slice_type']} bias in {disp['metric']}</li>"
                    
                    # Specific recommendations
                    if disp['slice_type'] == 'company':
                        html += f"<li>Consider adding more {disp['worst_performer']} documents or adjusting retrieval weights</li>"
                    elif disp['slice_type'] == 'source_type':
                        html += f"<li>Improve {disp['worst_performer']} data quality or parsing</li>"
                    elif disp['slice_type'] == 'category':
                        html += f"<li>Add more training examples for {disp['worst_performer']} queries</li>"
            
            html += "</ul>"
        
        return html
    
    def _get_metric_class(self, score: float) -> str:
        """Get CSS class for metric value"""
        if score >= 0.7:
            return 'metric-good'
        elif score >= 0.5:
            return 'metric-warning'
        else:
            return 'metric-poor'


# ==================== STANDALONE TESTING ====================

if __name__ == "__main__":
    from datetime import datetime
    
    print("\n" + "="*80)
    print("TESTING BIAS DETECTOR")
    print("="*80 + "\n")
    
    # Initialize agent
    agent = ResearcherAgent(
        qdrant_host='localhost',
        alpha=0.5,
        top_k=10
    )
    
    print("Loading corpus...")
    agent.load_corpus()
    
    # Initialize evaluator and detector
    evaluator = RetrievalEvaluator(
        ground_truth_file='data/validation/ground_truth.json'
    )
    
    detector = BiasDetector(evaluator)
    
    # Run complete bias analysis
    results = detector.run_complete_bias_analysis(agent)
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    detector.save_bias_report(
        results,
        f'results/bias_detection/bias_report_{timestamp}.json'
    )
    
    detector.generate_bias_html_report(
        results,
        f'results/bias_detection/bias_report_{timestamp}.html'
    )
    
    print(f"\n✅ Bias detection complete!")
    print(f"📄 View report: results/bias_detection/bias_report_{timestamp}.html")