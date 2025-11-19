# src/data_quality/bias_detector.py
"""Detects bias in data collection and representation"""

from typing import Dict, Any, List
from collections import Counter

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.vector_store_manager import VectorStoreManager
from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class BiasDetector:
    """
    Detects bias in data representation
    
    Analyzes:
    - Sector distribution (diversity)
    - Data volume per company (balance)
    - Source type balance (SEC vs Wikipedia vs News)
    - Temporal coverage
    """
    
    def __init__(self):
        """Initialize bias detector"""
        self.vector_store = VectorStoreManager()
        logger.info("BiasDetector initialized")
    
    def analyze_sector_distribution(self) -> Dict[str, Any]:
        """
        Analyze sector diversity (PRODUCTION-READY)
        
        Returns:
            Sector distribution report
        """
        logger.info("Analyzing sector distribution")
        
        all_companies = config.companies
        
        # Count by sector
        sectors = [company.get('sector', 'Unknown') for company in all_companies]
        sector_counts = Counter(sectors)
        
        # Calculate percentages
        total = len(all_companies)
        sector_distribution = {
            sector: {
                "count": count,
                "percentage": count / total * 100
            }
            for sector, count in sector_counts.items()
        }
        
        # Check for over-representation (>50% from one sector)
        max_sector = max(sector_counts.items(), key=lambda x: x[1])
        is_biased = (max_sector[1] / total) > 0.5
        
        report = {
            "total_companies": total,
            "unique_sectors": len(sector_counts),
            "distribution": sector_distribution,
            "dominant_sector": max_sector[0],
            "dominant_percentage": max_sector[1] / total * 100,
            "is_biased": is_biased
        }
        
        if is_biased:
            logger.warning(
                f"⚠️ Sector bias detected: {max_sector[0]} = {max_sector[1]/total*100:.1f}%"
            )
        
        return report
    
    def analyze_data_volume_balance(self) -> Dict[str, Any]:
        """
        Analyze if data volume is balanced across companies (PRODUCTION-READY)
        
        Returns:
            Data volume balance report
        """
        logger.info("Analyzing data volume balance")
        
        all_companies = config.companies
        company_chunks = []
        
        for company in all_companies:
            ticker = company['ticker']
            
            # Count chunks for this company
            chunk_count = self.vector_store.count_chunks(
                filters={"ticker": ticker}
            )
            
            company_chunks.append({
                "ticker": ticker,
                "chunk_count": chunk_count
            })
        
        # Calculate statistics
        counts = [c['chunk_count'] for c in company_chunks if c['chunk_count'] > 0]
        
        if not counts:
            return {"error": "No data available"}
        
        import numpy as np
        mean_chunks = np.mean(counts)
        std_chunks = np.std(counts)
        min_chunks = min(counts)
        max_chunks = max(counts)
        
        # Check for imbalance (if max > 3x mean)
        is_imbalanced = max_chunks > (mean_chunks * 3)
        
        report = {
            "companies_analyzed": len(counts),
            "mean_chunks": mean_chunks,
            "std_chunks": std_chunks,
            "min_chunks": min_chunks,
            "max_chunks": max_chunks,
            "is_imbalanced": is_imbalanced,
            "company_breakdown": company_chunks
        }
        
        if is_imbalanced:
            logger.warning(
                f"⚠️ Data volume imbalance: max={max_chunks}, mean={mean_chunks:.1f}"
            )
        
        return report
    
    def analyze_source_balance(self) -> Dict[str, Any]:
        """
        Analyze balance across data sources (PRODUCTION-READY)
        
        Returns:
            Source balance report
        """
        logger.info("Analyzing source type balance")
        
        # Count chunks by source type
        sec_count = self.vector_store.count_chunks(
            filters={"source_type": "sec_filing"}
        )
        wiki_count = self.vector_store.count_chunks(
            filters={"source_type": "wikipedia"}
        )
        news_count = self.vector_store.count_chunks(
            filters={"source_type": "news"}
        )
        
        total = sec_count + wiki_count + news_count
        
        if total == 0:
            return {"error": "No data in vector DB"}
        
        report = {
            "total_chunks": total,
            "sec_filing": {
                "count": sec_count,
                "percentage": sec_count / total * 100
            },
            "wikipedia": {
                "count": wiki_count,
                "percentage": wiki_count / total * 100
            },
            "news": {
                "count": news_count,
                "percentage": news_count / total * 100
            }
        }
        
        logger.info(
            f"Source balance: SEC={sec_count}, Wiki={wiki_count}, News={news_count}"
        )
        
        return report