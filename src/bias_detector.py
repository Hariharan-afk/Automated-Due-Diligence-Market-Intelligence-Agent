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
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BiasDetector:
    """Detect and analyze bias in collected data using data slicing"""
    
    def __init__(self):
        self.slicing_features = ['source', 'published_date', 'fiscal_year', 'filing_type']
        self.fairness_metrics = {}
        self.sec_expected_sections = {
            '10-K': 4,  # Items 1, 1A, 7, 8
            '10-Q': 3   # part1item1, part1item2, part2item1a
        }
    
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
        sec_filings = data.get('sec_filings', {})

        if not news_articles and not sec_filings:
            return {
                "error": "No data to analyze",
                "bias_detected": False
            }

        # Analyze news articles
        news_analysis = {}
        if news_articles:
            # Convert to DataFrame for easier analysis
            df = pd.DataFrame(news_articles)

            # Perform slicing analysis
            news_analysis = {
                "source_distribution": self._analyze_by_source(df),
                "temporal_distribution": self._analyze_by_time(df),
                "quality_across_slices": self._analyze_quality_across_slices(df)
            }

        # Analyze SEC filings
        sec_analysis = {}
        if sec_filings:
            sec_analysis = {
                "fiscal_year_distribution": self._analyze_sec_fiscal_years(sec_filings),
                "filing_type_coverage": self._analyze_sec_filing_types(sec_filings),
                "section_completeness": self._analyze_sec_sections(sec_filings),
                "company_size_indicators": self._analyze_sec_complexity(sec_filings)
            }

        # Calculate fairness metrics
        fairness_scores = self._calculate_fairness_metrics(
            news_analysis.get("source_distribution", {}),
            news_analysis.get("temporal_distribution", {}),
            sec_analysis
        )

        # Detect bias
        bias_findings = self._detect_bias_issues(
            news_analysis.get("source_distribution", {}),
            news_analysis.get("temporal_distribution", {}),
            news_analysis.get("quality_across_slices", {}),
            sec_analysis
        )

        # Generate report
        report = {
            "company_name": data.get('company_name'),
            "total_articles": len(news_articles),
            "total_sec_filings": len([f for f in sec_filings.values() if f and "error" not in f]),
            "analysis": {
                "news": news_analysis,
                "sec": sec_analysis
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

    def _analyze_sec_fiscal_years(self, sec_filings: Dict) -> Dict:
        """Analyze distribution of fiscal years in SEC filings"""
        fiscal_years = []
        for filing_type, filing_data in sec_filings.items():
            if filing_data and "error" not in filing_data:
                fiscal_year = filing_data.get("fiscal_year", 0)
                if fiscal_year:
                    fiscal_years.append(fiscal_year)

        if not fiscal_years:
            return {"error": "No fiscal years found"}

        return {
            "years_covered": sorted(set(fiscal_years)),
            "years_count": len(set(fiscal_years)),
            "year_range": {
                "earliest": min(fiscal_years),
                "latest": max(fiscal_years),
                "span": max(fiscal_years) - min(fiscal_years) + 1
            },
            "distribution": dict(Counter(fiscal_years)),
            "is_continuous": self._check_fiscal_year_continuity(sorted(set(fiscal_years)))
        }

    def _analyze_sec_filing_types(self, sec_filings: Dict) -> Dict:
        """Analyze coverage of different filing types"""
        filing_types_present = []
        filing_details = {}

        for filing_type, filing_data in sec_filings.items():
            if filing_data and "error" not in filing_data:
                filing_types_present.append(filing_type)
                filing_details[filing_type] = {
                    "fiscal_year": filing_data.get("fiscal_year"),
                    "sections_count": len(filing_data.get("sections", {})),
                    "total_words": filing_data.get("statistics", {}).get("total_words", 0),
                    "total_tables": filing_data.get("statistics", {}).get("total_tables", 0)
                }

        return {
            "types_available": filing_types_present,
            "coverage": {
                "has_10k": "10-K" in filing_types_present,
                "has_10q": "10-Q" in filing_types_present,
                "has_both": "10-K" in filing_types_present and "10-Q" in filing_types_present
            },
            "details": filing_details,
            "balance_score": 1.0 if len(filing_types_present) == 2 else 0.5
        }

    def _analyze_sec_sections(self, sec_filings: Dict) -> Dict:
        """Analyze completeness of sections within filings"""
        section_analysis = {}

        for filing_type, filing_data in sec_filings.items():
            if filing_data and "error" not in filing_data:
                sections = filing_data.get("sections", {})
                expected_count = self.sec_expected_sections.get(filing_type, 0)
                actual_count = len(sections)

                section_analysis[filing_type] = {
                    "expected_sections": expected_count,
                    "actual_sections": actual_count,
                    "completeness_ratio": actual_count / expected_count if expected_count > 0 else 0,
                    "missing_sections": expected_count - actual_count if actual_count < expected_count else 0,
                    "section_names": list(sections.keys())
                }

        return section_analysis

    def _analyze_sec_complexity(self, sec_filings: Dict) -> Dict:
        """Analyze company size/complexity indicators from SEC filings"""
        complexity_indicators = {}

        for filing_type, filing_data in sec_filings.items():
            if filing_data and "error" not in filing_data:
                stats = filing_data.get("statistics", {})

                complexity_indicators[filing_type] = {
                    "total_words": stats.get("total_words", 0),
                    "total_sections": stats.get("total_sections", 0),
                    "total_tables": stats.get("total_tables", 0),
                    "avg_words_per_section": (
                        stats.get("total_words", 0) / stats.get("total_sections", 1)
                        if stats.get("total_sections", 0) > 0 else 0
                    ),
                    "complexity_score": self._calculate_complexity_score(stats)
                }

        return complexity_indicators

    @staticmethod
    def _check_fiscal_year_continuity(years: List[int]) -> bool:
        """Check if fiscal years are continuous"""
        if len(years) <= 1:
            return True
        for i in range(len(years) - 1):
            if years[i + 1] - years[i] != 1:
                return False
        return True

    @staticmethod
    def _calculate_complexity_score(stats: Dict) -> float:
        """Calculate a complexity score based on filing statistics"""
        # Normalize metrics and combine
        words = min(stats.get("total_words", 0) / 100000, 1.0)  # Normalize to 100k words
        tables = min(stats.get("total_tables", 0) / 100, 1.0)   # Normalize to 100 tables
        sections = min(stats.get("total_sections", 0) / 10, 1.0)  # Normalize to 10 sections

        return (words * 0.5 + tables * 0.3 + sections * 0.2)

    def _calculate_fairness_metrics(self, source_analysis: Dict, temporal_analysis: Dict, sec_analysis: Dict = None) -> Dict:
        """Calculate fairness metrics"""
        fairness = {}

        # News metrics
        if source_analysis:
            # Source diversity (inverse of concentration)
            herfindahl = source_analysis.get('herfindahl_index', 1.0)
            fairness['source_diversity_score'] = 1 - herfindahl

        if temporal_analysis:
            # Temporal balance (inverse of standard deviation)
            temporal_std = temporal_analysis.get('articles_per_month', {}).get('std', 0)
            temporal_mean = temporal_analysis.get('articles_per_month', {}).get('mean', 1)
            fairness['temporal_balance_score'] = 1 - min(temporal_std / temporal_mean, 1) if temporal_mean > 0 else 0

        # SEC filing metrics
        if sec_analysis:
            # Filing type balance
            filing_coverage = sec_analysis.get('filing_type_coverage', {})
            fairness['filing_type_balance_score'] = filing_coverage.get('balance_score', 0)

            # Section completeness
            section_completeness = sec_analysis.get('section_completeness', {})
            if section_completeness:
                completeness_ratios = [
                    filing_info['completeness_ratio']
                    for filing_info in section_completeness.values()
                ]
                fairness['sec_completeness_score'] = statistics.mean(completeness_ratios) if completeness_ratios else 0
            else:
                fairness['sec_completeness_score'] = 0

        # Overall fairness score (0-100)
        scores = []
        weights = []

        if 'source_diversity_score' in fairness:
            scores.append(fairness['source_diversity_score'])
            weights.append(0.3)

        if 'temporal_balance_score' in fairness:
            scores.append(fairness['temporal_balance_score'])
            weights.append(0.2)

        if 'filing_type_balance_score' in fairness:
            scores.append(fairness['filing_type_balance_score'])
            weights.append(0.3)

        if 'sec_completeness_score' in fairness:
            scores.append(fairness['sec_completeness_score'])
            weights.append(0.2)

        if scores:
            fairness['overall_fairness_score'] = sum(s * w for s, w in zip(scores, weights)) / sum(weights) * 100
        else:
            fairness['overall_fairness_score'] = 0

        return fairness
    
    def _detect_bias_issues(self, source_analysis: Dict, temporal_analysis: Dict, quality_analysis: Dict, sec_analysis: Dict = None) -> List[Dict]:
        """Detect specific bias issues"""
        findings = []

        # News article bias detection
        if source_analysis:
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

        if temporal_analysis:
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

        if quality_analysis:
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

        # SEC filing bias detection
        if sec_analysis:
            # Filing type coverage bias
            filing_coverage = sec_analysis.get('filing_type_coverage', {})
            if filing_coverage and not filing_coverage.get('coverage', {}).get('has_both', False):
                missing_types = []
                if not filing_coverage['coverage'].get('has_10k'):
                    missing_types.append('10-K')
                if not filing_coverage['coverage'].get('has_10q'):
                    missing_types.append('10-Q')

                if missing_types:
                    findings.append({
                        "type": "incomplete_filing_coverage",
                        "severity": "medium",
                        "description": f"Missing filing types: {', '.join(missing_types)}",
                        "metric": "filing_type_balance",
                        "value": filing_coverage.get('balance_score', 0),
                        "threshold": 1.0
                    })

            # Section completeness bias
            section_completeness = sec_analysis.get('section_completeness', {})
            for filing_type, filing_info in section_completeness.items():
                completeness_ratio = filing_info.get('completeness_ratio', 0)
                if completeness_ratio < 0.75:
                    findings.append({
                        "type": "incomplete_sections",
                        "severity": "high" if completeness_ratio < 0.5 else "medium",
                        "description": f"{filing_type} missing {filing_info.get('missing_sections', 0)} sections ({completeness_ratio*100:.1f}% complete)",
                        "metric": "section_completeness",
                        "value": completeness_ratio,
                        "threshold": 0.75
                    })

            # Fiscal year continuity
            fiscal_years = sec_analysis.get('fiscal_year_distribution', {})
            if fiscal_years and not fiscal_years.get('error'):
                if not fiscal_years.get('is_continuous', True):
                    findings.append({
                        "type": "discontinuous_fiscal_years",
                        "severity": "low",
                        "description": f"Fiscal years not continuous: {fiscal_years.get('years_covered', [])}",
                        "metric": "fiscal_year_continuity",
                        "value": 0,
                        "threshold": 1
                    })

        return findings
    
    def _generate_recommendations(self, findings: List[Dict]) -> List[str]:
        """Generate mitigation recommendations"""
        recommendations = []

        finding_types = {f['type'] for f in findings}

        # News-related recommendations
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

        # SEC-related recommendations
        if 'incomplete_filing_coverage' in finding_types:
            recommendations.append(
                "Fetch both 10-K and 10-Q filings to ensure comprehensive SEC coverage"
            )

        if 'incomplete_sections' in finding_types:
            recommendations.append(
                "Verify SEC API extraction configuration to ensure all required sections are fetched"
            )

        if 'discontinuous_fiscal_years' in finding_types:
            recommendations.append(
                "Consider fetching filings for missing fiscal years to provide complete historical context"
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
        """Save bias analysis report with permission-safe approach"""
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
        
        # Create directory if it doesn't exist
        bias_reports_dir = Path("data/bias_reports")
        bias_reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert all numpy/pandas types to JSON-serializable types
        serializable_report = convert_to_json_serializable(report)
        
        filename = bias_reports_dir / f"{report['company_name'].replace(' ', '_')}_bias_report.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(serializable_report, f, indent=4, ensure_ascii=False)
            logger.info(f"💾 Bias report saved to: {filename}")
        except PermissionError as e:
            logger.warning(f"⚠️ Could not save bias report: {e}")


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