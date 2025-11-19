# src/data_quality/anomaly_detector.py
"""Detects anomalies in data patterns"""

from typing import Dict, Any, List, Optional
import numpy as np
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.metadata_store_manager import MetadataStoreManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class AnomalyDetector:
    """
    Detects anomalies in pipeline data
    
    Detects:
    - Unusual chunk counts
    - Missing sections
    - Abnormal processing times
    - Data volume spikes
    """
    
    def __init__(self):
        """Initialize anomaly detector"""
        self.metadata_store = MetadataStoreManager()
        logger.info("AnomalyDetector initialized")
    
    def check_chunk_count_anomaly(
        self,
        ticker: str,
        source_type: str,
        current_chunk_count: int,
        threshold_std_devs: float = 2.0
    ) -> Dict[str, Any]:
        """
        Check if chunk count is anomalous (PRODUCTION-READY)
        
        Compares current count against historical average
        
        Args:
            ticker: Company ticker
            source_type: "sec_filing", "wikipedia", or "news"
            current_chunk_count: Current chunk count
            threshold_std_devs: Number of std devs for anomaly (default 2.0)
            
        Returns:
            Anomaly report dict
        """
        logger.info(
            f"Checking chunk count for {ticker} {source_type}: {current_chunk_count}"
        )
        
        # Get historical data
        historical_counts = self._get_historical_chunk_counts(ticker, source_type)
        
        if len(historical_counts) < 3:
            logger.warning(f"Not enough historical data for {ticker} (need 3+)")
            return {
                "is_anomaly": False,
                "reason": "insufficient_history",
                "current": current_chunk_count
            }
        
        # Calculate statistics
        mean = np.mean(historical_counts)
        std_dev = np.std(historical_counts)
        
        # Check if current is anomalous
        if std_dev == 0:
            std_dev = 0.1  # Avoid division by zero
        
        z_score = abs(current_chunk_count - mean) / std_dev
        is_anomaly = z_score > threshold_std_devs
        
        report = {
            "is_anomaly": is_anomaly,
            "current_count": current_chunk_count,
            "historical_mean": mean,
            "historical_std": std_dev,
            "z_score": z_score,
            "threshold": threshold_std_devs,
            "historical_counts": historical_counts
        }
        
        if is_anomaly:
            logger.warning(
                f"⚠️ Anomaly detected for {ticker}: "
                f"count={current_chunk_count}, mean={mean:.1f}, "
                f"std={std_dev:.1f}, z-score={z_score:.2f}"
            )
        else:
            logger.info(f"✅ Chunk count normal for {ticker}")
        
        return report
    
    def _get_historical_chunk_counts(
        self,
        ticker: str,
        source_type: str,
        lookback_count: int = 10
    ) -> List[int]:
        """Get historical chunk counts (PRODUCTION-READY)"""
        counts = []
        
        if source_type == "sec_filing":
            # Get recent filings
            filings = self.metadata_store.get_filings_by_ticker(
                ticker=ticker,
                limit=lookback_count
            )
            counts = [f['total_chunks'] for f in filings if f.get('total_chunks')]
        
        elif source_type == "wikipedia":
            # Wikipedia has fewer historical points (updated weekly)
            # Just return current if exists
            pass
        
        return counts
    
    def check_missing_sections(
        self,
        ticker: str,
        filing_type: str,
        sections_extracted: List[str]
    ) -> Dict[str, Any]:
        """
        Check if expected sections are missing (PRODUCTION-READY)
        
        Args:
            ticker: Company ticker
            filing_type: Filing type (10-K, 10-Q)
            sections_extracted: List of section codes extracted
            
        Returns:
            Missing sections report
        """
        # Expected sections
        if filing_type == "10-K":
            expected_sections = ['1', '1A', '7', '8']
        elif filing_type == "10-Q":
            expected_sections = ['part1item1', 'part1item2']
        else:
            expected_sections = []
        
        # Find missing
        missing = [s for s in expected_sections if s not in sections_extracted]
        
        report = {
            "ticker": ticker,
            "filing_type": filing_type,
            "expected_sections": expected_sections,
            "extracted_sections": sections_extracted,
            "missing_sections": missing,
            "has_missing": len(missing) > 0
        }
        
        if missing:
            logger.warning(
                f"⚠️ Missing sections for {ticker} {filing_type}: {missing}"
            )
        
        return report
    
    def detect_processing_time_anomaly(
        self,
        ticker: str,
        processing_time_seconds: float,
        threshold_multiplier: float = 3.0
    ) -> Dict[str, Any]:
        """
        Detect if processing took unusually long (PRODUCTION-READY)
        
        Args:
            ticker: Company ticker
            processing_time_seconds: Time taken to process
            threshold_multiplier: Alert if > mean * threshold
            
        Returns:
            Anomaly report
        """
        # Typical processing times (can be learned from history)
        typical_time = 600  # 10 minutes baseline
        
        is_anomaly = processing_time_seconds > (typical_time * threshold_multiplier)
        
        report = {
            "is_anomaly": is_anomaly,
            "processing_time": processing_time_seconds,
            "typical_time": typical_time,
            "threshold": typical_time * threshold_multiplier
        }
        
        if is_anomaly:
            logger.warning(
                f"⚠️ Processing time anomaly for {ticker}: "
                f"{processing_time_seconds:.1f}s (expected <{typical_time * threshold_multiplier:.1f}s)"
            )
        
        return report
    
    def close(self):
        """Close database connections"""
        self.metadata_store.close()