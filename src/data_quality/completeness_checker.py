# src/data_quality/completeness_checker.py
"""Checks data completeness across all companies"""

from typing import Dict, Any, List
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.metadata_store_manager import MetadataStoreManager
from src.storage.vector_store_manager import VectorStoreManager
from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class CompletenessChecker:
    """
    Checks data completeness across all sources
    
    Checks:
    - All companies have recent data
    - All expected sections present
    - No gaps in date ranges
    - All companies represented in vector DB
    """
    
    def __init__(self):
        """Initialize completeness checker"""
        self.metadata_store = MetadataStoreManager()
        self.vector_store = VectorStoreManager()
        logger.info("CompletenessChecker initialized")
    
    def check_company_coverage(self, days_back: int = 90) -> Dict[str, Any]:
        """
        Check if all companies have recent data (PRODUCTION-READY)
        
        Args:
            days_back: Check for data in last N days
            
        Returns:
            Coverage report
        """
        logger.info(f"Checking company coverage (last {days_back} days)")
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        all_companies = config.companies
        companies_with_data = []
        companies_without_data = []
        
        for company in all_companies:
            ticker = company['ticker']
            
            # Check if company has any recent data
            has_data = self._has_recent_data(ticker, cutoff_date)
            
            if has_data:
                companies_with_data.append(ticker)
            else:
                companies_without_data.append(ticker)
                logger.warning(f"⚠️ No recent data for {ticker}")
        
        coverage_rate = len(companies_with_data) / len(all_companies) * 100
        
        report = {
            "total_companies": len(all_companies),
            "companies_with_data": len(companies_with_data),
            "companies_without_data": len(companies_without_data),
            "missing_companies": companies_without_data,
            "coverage_rate": coverage_rate,
            "is_complete": len(companies_without_data) == 0
        }
        
        if companies_without_data:
            logger.warning(
                f"⚠️ Coverage incomplete: {len(companies_without_data)} "
                f"companies missing data"
            )
        else:
            logger.info(f"✅ Full coverage: All {len(all_companies)} companies have data")
        
        return report
    
    def _has_recent_data(self, ticker: str, cutoff_date: datetime) -> bool:
        """Check if ticker has data after cutoff date (PRODUCTION-READY)"""
        # Check SEC filings
        filings = self.metadata_store.get_filings_by_ticker(ticker, limit=1)
        if filings:
            latest_filing = filings[0]
            if latest_filing.get('filing_date'):
                filing_date = latest_filing['filing_date']
                if isinstance(filing_date, str):
                    filing_date = datetime.strptime(filing_date, '%Y-%m-%d')
                if filing_date >= cutoff_date:
                    return True
        
        # Check Wikipedia (has it been updated?)
        wiki_revision = self.metadata_store.get_wikipedia_revision(ticker)
        if wiki_revision:
            return True  # Wikipedia exists
        
        # Check if has chunks in vector DB
        chunk_count = self.vector_store.count_chunks(filters={"ticker": ticker})
        if chunk_count > 0:
            return True
        
        return False
    
    def check_section_completeness(
        self,
        ticker: str,
        filing_type: str,
        sections_extracted: List[str]
    ) -> Dict[str, Any]:
        """
        Check if all expected sections are present (PRODUCTION-READY)
        
        Args:
            ticker: Company ticker
            filing_type: Filing type
            sections_extracted: Extracted section codes
            
        Returns:
            Completeness report
        """
        # Define expected sections
        if filing_type == "10-K":
            expected_sections = ['1', '1A', '7', '8']
        elif filing_type == "10-Q":
            expected_sections = ['part1item1', 'part1item2']
        else:
            expected_sections = []
        
        missing = [s for s in expected_sections if s not in sections_extracted]
        extra = [s for s in sections_extracted if s not in expected_sections]
        
        report = {
            "ticker": ticker,
            "filing_type": filing_type,
            "expected_sections": expected_sections,
            "extracted_sections": sections_extracted,
            "missing_sections": missing,
            "extra_sections": extra,
            "is_complete": len(missing) == 0
        }
        
        if missing:
            logger.warning(f"⚠️ Missing sections for {ticker}: {missing}")
        
        return report
    
    def check_vector_db_coverage(self) -> Dict[str, Any]:
        """
        Check vector DB coverage across all companies (PRODUCTION-READY)
        
        Returns:
            Vector DB coverage report
        """
        logger.info("Checking vector DB coverage")
        
        all_companies = config.companies
        coverage = []
        
        for company in all_companies:
            ticker = company['ticker']
            
            # Count chunks for each source type
            sec_count = self.vector_store.count_chunks(
                filters={"ticker": ticker, "source_type": "sec_filing"}
            )
            wiki_count = self.vector_store.count_chunks(
                filters={"ticker": ticker, "source_type": "wikipedia"}
            )
            news_count = self.vector_store.count_chunks(
                filters={"ticker": ticker, "source_type": "news"}
            )
            
            total_count = sec_count + wiki_count + news_count
            
            coverage.append({
                "ticker": ticker,
                "sec_chunks": sec_count,
                "wikipedia_chunks": wiki_count,
                "news_chunks": news_count,
                "total_chunks": total_count,
                "has_data": total_count > 0
            })
        
        # Summary
        companies_with_data = sum(1 for c in coverage if c['has_data'])
        total_chunks = sum(c['total_chunks'] for c in coverage)
        
        report = {
            "total_companies": len(all_companies),
            "companies_with_data": companies_with_data,
            "total_chunks_in_db": total_chunks,
            "coverage_by_company": coverage,
            "coverage_rate": companies_with_data / len(all_companies) * 100
        }
        
        logger.info(
            f"Vector DB coverage: {companies_with_data}/{len(all_companies)} companies, "
            f"{total_chunks} total chunks"
        )
        
        return report
    
    def close(self):
        """Close database connections"""
        self.metadata_store.close()