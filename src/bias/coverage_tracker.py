"""
Coverage Tracker Module

Tracks data coverage metrics for each company to identify
representation bias and enable fair retrieval boosting.
"""

import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from collections import defaultdict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class CoverageTracker:
    """
    Tracks and stores coverage metrics for each company
    
    Metrics tracked:
    - Total chunks per company
    - Chunks per data source (SEC, Wikipedia, News)
    - Number of tables extracted
    - Quality indicators
    """
    
    def __init__(self, storage_path: Path):
        """
        Initialize coverage tracker
        
        Args:
            storage_path: Path to store coverage metrics JSON
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing metrics or initialize
        self.metrics = self._load_metrics()
        
        logger.info(f"CoverageTracker initialized: {len(self.metrics)} companies tracked")
    
    def _load_metrics(self) -> Dict[str, Dict]:
        """Load existing coverage metrics from storage"""
        if self.storage_path.exists():
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_metrics(self):
        """Save coverage metrics to storage"""
        with open(self.storage_path, 'w') as f:
            json.dump(self.metrics, f, indent=2)
        logger.debug(f"Saved metrics for {len(self.metrics)} companies")
    
    def track_company(
        self,
        ticker: str,
        company_name: str,
        chunks: List[Dict[str, Any]],
        num_tables: int = 0,
        metadata: Dict[str, Any] = None
    ):
        """
        Track coverage metrics for a company
        
        Args:
            ticker: Company ticker
            company_name: Full company name
            chunks: List of all chunks for this company
            num_tables: Number of tables extracted
            metadata: Additional metadata (filing date, etc.)
        """
        # Count chunks by source
        source_distribution = defaultdict(int)
        for chunk in chunks:
            source = chunk.get('data_source', 'unknown')
            source_distribution[source] += 1
        
        # Calculate quality metrics
        avg_chunk_length = sum(c.get('chunk_length', 0) for c in chunks) / len(chunks) if chunks else 0
        
        # Check for required data sources
        has_sec = source_distribution.get('sec', 0) > 0
        has_wiki = source_distribution.get('wikipedia', 0) > 0
        has_news = source_distribution.get('news', 0) > 0
        
        # Calculate completeness score (0-1)
        completeness = (
            0.5 * (1 if has_sec else 0) +      # SEC most important
            0.2 * (1 if has_wiki else 0) +     # Wiki medium
            0.3 * (1 if has_news else 0)       # News important for current info
        )
        
        # Store metrics
        company_metrics = {
            'ticker': ticker,
            'company_name': company_name,
            'total_chunks': len(chunks),
            'source_distribution': dict(source_distribution),
            'num_tables': num_tables,
            'avg_chunk_length': avg_chunk_length,
            'completeness_score': completeness,
            'has_sec': has_sec,
            'has_wikipedia': has_wiki,
            'has_news': has_news,
            'last_updated': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        self.metrics[ticker] = company_metrics
        self._save_metrics()
        
        logger.info(
            f"Tracked {ticker}: {len(chunks)} chunks "
            f"(SEC:{source_distribution['sec']}, "
            f"Wiki:{source_distribution['wikipedia']}, "
            f"News:{source_distribution['news']}), "
            f"completeness={completeness:.2f}"
        )
        
        return company_metrics
    
    def get_company_metrics(self, ticker: str) -> Dict[str, Any]:
        """Get metrics for a specific company"""
        return self.metrics.get(ticker, None)
    
    def get_all_metrics(self) -> Dict[str, Dict]:
        """Get metrics for all tracked companies"""
        return self.metrics
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics across all companies"""
        if not self.metrics:
            return {
                'total_companies': 0,
                'avg_chunks': 0,
                'avg_completeness': 0
            }
        
        total_chunks = [m['total_chunks'] for m in self.metrics.values()]
        completeness_scores = [m['completeness_score'] for m in self.metrics.values()]
        
        return {
            'total_companies': len(self.metrics),
            'avg_total_chunks': sum(total_chunks) / len(total_chunks),
            'min_chunks': min(total_chunks),
            'max_chunks': max(total_chunks),
            'avg_completeness': sum(completeness_scores) / len(completeness_scores),
            'companies_with_sec': sum(1 for m in self.metrics.values() if m['has_sec']),
            'companies_with_wiki': sum(1 for m in self.metrics.values() if m['has_wikipedia']),
            'companies_with_news': sum(1 for m in self.metrics.values() if m['has_news'])
        }
    
    def export_report(self, output_path: Path):
        """
        Export detailed coverage report
        
        Args:
            output_path: Path to save the report
        """
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': self.get_summary_stats(),
            'companies': self.metrics
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Exported coverage report to {output_path}")
        
        return report
