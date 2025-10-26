"""
Bias Detection Module - FINAL VERSION
Implements data slicing and fairness analysis
"""

import pandas as pd
import numpy as np
import json
import logging
from typing import Dict, List
from datetime import datetime
from collections import Counter
import statistics
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BiasDetector:
    """Detect and analyze bias in collected data using data slicing"""
    
    def __init__(self):
        self.slicing_features = ['source', 'published_date']
        self.fairness_metrics = {}
    
    def analyze_data(self, data: Dict) -> Dict:
        """
        Perform comprehensive bias analysis on data
        
        Args:
            data: Processed company data
            
        Returns:
            Dictionary with bias analysis results
        """
        logger.info(f"🔍 Analyzing bias for: {data.get('company_name')}")
        
        news_articles = data.get('news_articles', [])
        
        if not news_articles:
            return {
                "error": "No news articles to analyze",
                "bias_detected": False
            }
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(news_articles)
        
        # Perform slicing analysis
        source_analysis = self._analyze_by_source(df)
        temporal_analysis = self._analyze_by_time(df)
        quality_analysis = self._analyze_quality_across_slices(df)
        
        # Calculate fairness metrics
        fairness_scores = self._calculate_fairness_metrics(
            source_analysis, temporal_analysis
        )
        
        # Detect bias
        bias_findings = self._detect_bias_issues(
            source_analysis, temporal_analysis, quality_analysis
        )
        
        # Generate report
        report = {
            "company_name": data.get('company_name'),
            "total_articles": len(news_articles),
            "analysis": {
                "source_distribution": source_analysis,
                "temporal_distribution": temporal_analysis,
                "quality_across_slices": quality_analysis
            },
            "fairness_metrics": fairness_scores,
            "bias_findings": bias_findings,
            "bias_detected": len(bias_findings) > 0,
            "recommendations": self._generate_recommendations(bias_findings),
            "timestamp": datetime.now().isoformat()
        }
        
        # Save report
        self._save_report(report)
        
        logger.info(f"✅ Bias analysis complete. Findings: {len(bias_findings)}")
        return report
    
    def _analyze_by_source(self, df: pd.DataFrame) -> Dict:
        """Analyze article distribution by source"""
        source_counts = df['source'].value_counts()
        total_articles = len(df)
        
        # Calculate statistics
        source_stats = {
            "total_sources": len(source_counts),
            "distribution": source_counts.to_dict(),
            "percentages": (source_counts / total_articles * 100).to_dict(),
            "top_3_sources": source_counts.head(3).to_dict(),
            "dominance_ratio": source_counts.iloc[0] / total_articles if len(source_counts) > 0 else 0
        }
        
        # Calculate diversity metrics
        source_stats["herfindahl_index"] = self._calculate_herfindahl_index(source_counts)
        source_stats["gini_coefficient"] = self._calculate_gini_coefficient(source_counts.values)
        
        return source_stats
    
    def _analyze_by_time(self, df: pd.DataFrame) -> Dict:
        """Analyze temporal distribution of articles"""
        # Convert dates
        df['date'] = pd.to_datetime(df['published_date'], errors='coerce')
        df = df.dropna(subset=['date'])
        
        if len(df) == 0:
            return {"error": "No valid dates found"}
        
        # Group by month
        df['month'] = df['date'].dt.to_period('M')
        monthly_counts = df['month'].value_counts().sort_index()
        
        # Calculate temporal statistics
        temporal_stats = {
            "date_range": {
                "earliest": df['date'].min().strftime('%Y-%m-%d'),
                "latest": df['date'].max().strftime('%Y-%m-%d'),
                "span_days": (df['date'].max() - df['date'].min()).days
            },
            "monthly_distribution": {str(k): v for k, v in monthly_counts.items()},
            "articles_per_month": {
                "mean": monthly_counts.mean(),
                "std": monthly_counts.std(),
                "min": monthly_counts.min(),
                "max": monthly_counts.max()
            },
            "recency_bias": self._calculate_recency_bias(df['date'])
        }
        
        return temporal_stats
    
    def _analyze_quality_across_slices(self, df: pd.DataFrame) -> Dict:
        """Analyze content quality across different slices"""
        quality_metrics = {}
        
        # Quality by source
        source_quality = df.groupby('source').agg({
            'word_count': ['mean', 'std', 'min', 'max'],
            'has_content': 'mean'
        }).to_dict()
        
        quality_metrics['by_source'] = {
            'word_count_stats': source_quality[('word_count', 'mean')],
            'content_availability': source_quality[('has_content', 'mean')]
        }
        
        # Overall quality variance
        word_counts = df['word_count'].dropna()
        if len(word_counts) > 0:
            quality_metrics['overall'] = {
                'mean_word_count': word_counts.mean(),
                'std_word_count': word_counts.std(),
                'coefficient_of_variation': word_counts.std() / word_counts.mean() if word_counts.mean() > 0 else 0
            }
        
        return quality_metrics
    
    def _calculate_fairness_metrics(self, source_analysis: Dict, temporal_analysis: Dict) -> Dict:
        """Calculate fairness metrics"""
        fairness = {}
        
        # Source diversity (inverse of concentration)
        herfindahl = source_analysis.get('herfindahl_index', 1.0)
        fairness['source_diversity_score'] = 1 - herfindahl
        
        # Temporal balance (inverse of standard deviation)
        temporal_std = temporal_analysis.get('articles_per_month', {}).get('std', 0)
        temporal_mean = temporal_analysis.get('articles_per_month', {}).get('mean', 1)
        fairness['temporal_balance_score'] = 1 - min(temporal_std / temporal_mean, 1) if temporal_mean > 0 else 0
        
        # Overall fairness score (0-100)
        fairness['overall_fairness_score'] = (
            fairness['source_diversity_score'] * 0.5 +
            fairness['temporal_balance_score'] * 0.5
        ) * 100
        
        return fairness
    
    def _detect_bias_issues(self, source_analysis: Dict, temporal_analysis: Dict, quality_analysis: Dict) -> List[Dict]:
        """Detect specific bias issues"""
        findings = []
        
        # Source dominance bias
        dominance_ratio = source_analysis.get('dominance_ratio', 0)
        if dominance_ratio > 0.5:
            findings.append({
                "type": "source_dominance",
                "severity": "high",
                "description": f"Single source dominates with {dominance_ratio*100:.1f}% of articles",
                "metric": "dominance_ratio",
                "value": dominance_ratio,
                "threshold": 0.5
            })
        
        # Low source diversity
        total_sources = source_analysis.get('total_sources', 0)
        if total_sources < 3:
            findings.append({
                "type": "low_source_diversity",
                "severity": "medium",
                "description": f"Only {total_sources} unique sources found",
                "metric": "source_count",
                "value": total_sources,
                "threshold": 3
            })
        
        # Recency bias
        recency_bias = temporal_analysis.get('recency_bias', 0)
        if recency_bias > 0.7:
            findings.append({
                "type": "recency_bias",
                "severity": "medium",
                "description": f"{recency_bias*100:.1f}% of articles from last 30 days",
                "metric": "recent_article_ratio",
                "value": recency_bias,
                "threshold": 0.7
            })
        
        # Quality variance across sources
        quality_by_source = quality_analysis.get('by_source', {}).get('word_count_stats', {})
        if quality_by_source:
            word_counts = list(quality_by_source.values())
            if len(word_counts) > 1 and statistics.stdev(word_counts) / statistics.mean(word_counts) > 0.5:
                findings.append({
                    "type": "quality_variance",
                    "severity": "low",
                    "description": "Significant quality variance across sources",
                    "metric": "quality_cv",
                    "value": statistics.stdev(word_counts) / statistics.mean(word_counts),
                    "threshold": 0.5
                })
        
        return findings
    
    def _generate_recommendations(self, findings: List[Dict]) -> List[str]:
        """Generate mitigation recommendations"""
        recommendations = []
        
        finding_types = {f['type'] for f in findings}
        
        if 'source_dominance' in finding_types:
            recommendations.append(
                "Increase diversity of news sources by adding more RSS feeds or APIs"
            )
        
        if 'low_source_diversity' in finding_types:
            recommendations.append(
                "Expand data collection to include more news providers"
            )
        
        if 'recency_bias' in finding_types:
            recommendations.append(
                "Adjust time window to include historical articles for better temporal balance"
            )
        
        if 'quality_variance' in finding_types:
            recommendations.append(
                "Implement minimum quality thresholds consistently across all sources"
            )
        
        if not recommendations:
            recommendations.append("No significant bias detected. Continue current practices.")
        
        return recommendations
    
    @staticmethod
    def _calculate_herfindahl_index(counts: pd.Series) -> float:
        """Calculate Herfindahl-Hirschman Index (concentration measure)"""
        total = counts.sum()
        if total == 0:
            return 0
        shares = counts / total
        return (shares ** 2).sum()
    
    @staticmethod
    def _calculate_gini_coefficient(values) -> float:
        """Calculate Gini coefficient (inequality measure)"""
        sorted_values = sorted(values)
        n = len(sorted_values)
        if n == 0:
            return 0
        
        cumsum = 0
        for i, value in enumerate(sorted_values):
            cumsum += (n - i) * value
        
        return (2 * cumsum) / (n * sum(sorted_values)) - (n + 1) / n
    
    @staticmethod
    def _calculate_recency_bias(dates: pd.Series) -> float:
        """Calculate proportion of recent articles"""
        if len(dates) == 0:
            return 0
        
        latest_date = dates.max()
        thirty_days_ago = latest_date - pd.Timedelta(days=30)
        recent_count = (dates >= thirty_days_ago).sum()
        
        return recent_count / len(dates)
    
    @staticmethod
    def _save_report(report: Dict):
        """Save bias analysis report"""
        import numpy as np
        
        def convert_to_json_serializable(obj):
            """Convert numpy/pandas types to Python native types"""
            if isinstance(obj, dict):
                return {key: convert_to_json_serializable(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_json_serializable(item) for item in obj]
            elif isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif pd.isna(obj):
                return None
            else:
                return obj
        
        os.makedirs("data/bias_reports", exist_ok=True)
        
        # Convert all numpy/pandas types to JSON-serializable types
        serializable_report = convert_to_json_serializable(report)
        
        filename = f"data/bias_reports/{report['company_name'].replace(' ', '_')}_bias_report.json"
        with open(filename, 'w') as f:
            json.dump(serializable_report, f, indent=4)
        
        logger.info(f"💾 Bias report saved to: {filename}")


def main():
    """Example usage"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python bias_detector.py <processed_data_file.json>")
        sys.exit(1)
    
    data_file = sys.argv[1]
    
    if not os.path.exists(data_file):
        print(f"File not found: {data_file}")
        sys.exit(1)
    
    with open(data_file, 'r') as f:
        data = json.load(f)
    
    # Run bias analysis
    detector = BiasDetector()
    report = detector.analyze_data(data)
    
    # Print summary
    print("\n" + "="*60)
    print(f"Bias Analysis for: {report['company_name']}")
    print("="*60)
    print(f"\nTotal Articles: {report['total_articles']}")
    print(f"Unique Sources: {report['analysis']['source_distribution']['total_sources']}")
    print(f"Fairness Score: {report['fairness_metrics']['overall_fairness_score']:.1f}/100")
    print(f"\nBias Detected: {'Yes' if report['bias_detected'] else 'No'}")
    print(f"Findings: {len(report['bias_findings'])}")
    
    if report['bias_findings']:
        print("\nIssues Found:")
        for finding in report['bias_findings']:
            print(f"  - [{finding['severity'].upper()}] {finding['description']}")
    
    print("\nRecommendations:")
    for rec in report['recommendations']:
        print(f"  • {rec}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()