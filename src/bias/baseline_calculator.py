"""
Baseline Calculator Module

Calculates global baseline metrics and classifies companies
based on their data coverage relative to the baseline.
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class BaselineCalculator:
    """
    Calculates baseline metrics and classifies companies
    
    Uses statistical methods to determine:
    - Global average coverage
    - Coverage thresholds for small/medium/large companies
    - Source-specific baselines
    """
    
    def __init__(self, coverage_metrics: Dict[str, Dict]):
        """
        Initialize baseline calculator
        
        Args:
            coverage_metrics: Dict of company metrics from CoverageTracker
        """
        self.metrics = coverage_metrics
        self.baselines = None
        self.thresholds = None
        
        if self.metrics:
            self._calculate_baselines()
            self._calculate_thresholds()
    
    def _calculate_baselines(self):
        """Calculate global baseline metrics"""
        if not self.metrics:
            logger.warning("No metrics available for baseline calculation")
            return
        
        # Extract metrics for all companies
        total_chunks = [m['total_chunks'] for m in self.metrics.values()]
        sec_chunks = [m['source_distribution'].get('sec', 0) for m in self.metrics.values()]
        wiki_chunks = [m['source_distribution'].get('wikipedia', 0) for m in self.metrics.values()]
        news_chunks = [m['source_distribution'].get('news', 0) for m in self.metrics.values()]
        tables = [m['num_tables'] for m in self.metrics.values()]
        completeness = [m['completeness_score'] for m in self.metrics.values()]
        
        self.baselines = {
            'total_chunks': {
                'mean': np.mean(total_chunks),
                'median': np.median(total_chunks),
                'std': np.std(total_chunks),
                'min': np.min(total_chunks),
                'max': np.max(total_chunks)
            },
            'source_chunks': {
                'sec': {
                    'mean': np.mean(sec_chunks),
                    'median': np.median(sec_chunks)
                },
                'wikipedia': {
                    'mean': np.mean(wiki_chunks),
                    'median': np.median(wiki_chunks)
                },
                'news': {
                    'mean': np.mean(news_chunks),
                    'median': np.median(news_chunks)
                }
            },
            'tables': {
                'mean': np.mean(tables),
                'median': np.median(tables)
            },
            'completeness': {
                'mean': np.mean(completeness),
                'median': np.median(completeness)
            }
        }
        
        logger.info(
            f"Calculated baselines: avg_chunks={self.baselines['total_chunks']['mean']:.1f}, "
            f"median={self.baselines['total_chunks']['median']:.1f}"
        )
    
    def _calculate_thresholds(self):
        """Calculate thresholds for company classification using percentiles"""
        if not self.metrics:
            return
        
        total_chunks = [m['total_chunks'] for m in self.metrics.values()]
        
        # Use percentiles for robust threshold calculation
        self.thresholds = {
            'small': np.percentile(total_chunks, 33),    # Bottom 33%
            'medium': np.percentile(total_chunks, 67),   # Middle 33%
            # Above 67th percentile = large
        }
        
        logger.info(
            f"Calculated thresholds: small<{self.thresholds['small']:.0f}, "
            f"medium<{self.thresholds['medium']:.0f}"
        )
    
    def classify_company(
        self,
        company_metrics: Dict[str, Any],
        method: str = 'percentile'
    ) -> Tuple[str, float]:
        """
        Classify company based on coverage
        
        Args:
            company_metrics: Metrics for a specific company
            method: 'percentile' or 'ratio' based classification
        
        Returns:
            Tuple of (classification, coverage_ratio)
            classification: 'small', 'medium', or 'large'
            coverage_ratio: Ratio of company's chunks to baseline
        """
        if not self.baselines:
            logger.warning("Baselines not calculated, defaulting to 'medium'")
            return 'medium', 1.0
        
        total_chunks = company_metrics['total_chunks']
        
        if method == 'percentile':
            # Use pre-calculated percentile thresholds
            if total_chunks < self.thresholds['small']:
                classification = 'small'
            elif total_chunks < self.thresholds['medium']:
                classification = 'medium'
            else:
                classification = 'large'
        
        else:  # ratio method
            # Use ratio to mean baseline
            baseline_mean = self.baselines['total_chunks']['mean']
            ratio = total_chunks / baseline_mean if baseline_mean > 0 else 1.0
            
            if ratio < 0.6:
                classification = 'small'
            elif ratio < 1.0:
                classification = 'medium'
            else:
                classification = 'large'
        
        # Calculate coverage ratio for reporting
        baseline_mean = self.baselines['total_chunks']['mean']
        coverage_ratio = total_chunks / baseline_mean if baseline_mean > 0 else 1.0
        
        return classification, coverage_ratio
    
    def get_boost_factor(
        self,
        classification: str,
        source: str = None,
        quality_adjusted: bool = True,
        quality_score: float = 1.0
    ) -> float:
        """
        Get retrieval boost factor for a company
        
        Args:
            classification: 'small', 'medium', or 'large'
            source: Optional - adjust boost per source type
            quality_adjusted: Whether to adjust boost based on quality
            quality_score: Quality/completeness score (0-1)
        
        Returns:
            Boost factor to add to retrieval scores
        """
        # Base boost factors
        base_boosts = {
            'small': 0.25,
            'medium': 0.12,
            'large': 0.0
        }
        
        # Source-specific multipliers
        source_multipliers = {
            'sec': 0.8,        # SEC less affected by size
            'wikipedia': 0.6,  # Wiki moderately affected
            'news': 1.2        # News most affected by company size
        }
        
        # Get base boost
        boost = base_boosts.get(classification, 0.0)
        
        # Apply source multiplier if specified
        if source:
            multiplier = source_multipliers.get(source, 1.0)
            boost *= multiplier
        
        # Adjust for quality (reduce boost for low-quality data)
        if quality_adjusted and quality_score < 0.7:
            quality_penalty = quality_score / 0.7  # Scale: 0.0-1.0
            boost *= quality_penalty
        
        return boost
    
    def get_baselines(self) -> Dict:
        """Get calculated baseline metrics"""
        return self.baselines
    
    def get_thresholds(self) -> Dict:
        """Get classification thresholds"""
        return self.thresholds
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive baseline report"""
        if not self.metrics or not self.baselines:
            return {'error': 'No data available'}
        
        # Classify all companies
        classifications = {
            'small': [],
            'medium': [],
            'large': []
        }
        
        for ticker, metrics in self.metrics.items():
            classification, ratio = self.classify_company(metrics)
            classifications[classification].append({
                'ticker': ticker,
                'chunks': metrics['total_chunks'],
                'ratio': ratio
            })
        
        return {
            'baselines': self.baselines,
            'thresholds': self.thresholds,
            'classification_counts': {
                cls: len(companies) for cls, companies in classifications.items()
            },
            'classifications': classifications
        }
    
    def save_baseline_config(self, output_path: Path):
        """Save baseline configuration for use in retrieval"""
        config = {
            'baselines': self.baselines,
            'thresholds': self.thresholds,
            'generated_at': np.datetime64('now').astype(str)
        }
        
        with open(output_path, 'w') as f:
            # Convert numpy types to native Python for JSON serialization
            def convert(obj):
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                return obj
            
            json.dump(config, f, indent=2, default=convert)
        
        logger.info(f"Saved baseline config to {output_path}")
