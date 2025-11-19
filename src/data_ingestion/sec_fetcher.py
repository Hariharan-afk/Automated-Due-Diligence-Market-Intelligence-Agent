# src/data_ingestion/sec_fetcher.py
"""
SEC Filings Fetcher using sec-api.io

Fetches 10-K and 10-Q filings with section extraction.
Uses Query API to find filings and Extractor API to get sections.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
import time
import hashlib

from sec_api import QueryApi, ExtractorApi

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data_ingestion.base_fetcher import BaseFetcher
from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SECFetcher(BaseFetcher):
    """
    Fetches SEC filings and extracts sections using sec-api.io
    
    Features:
    - Queries filings by ticker, date range, filing type
    - Extracts specific sections from each filing
    - Caches query results and extracted sections
    - Handles pagination automatically
    - Strict error mode: skips filing if any section fails
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize SEC fetcher
        
        Args:
            api_key: SEC API key (loads from config if None)
        """
        # Initialize base class with rate limiting
        super().__init__(
            rate_limit=config.api.sec_rate_limit,
            max_retries=3,
            base_delay=1.0
        )
        
        # Load API key from config or parameter
        self.api_key = api_key or config.api.sec_api_key
        
        if not self.api_key:
            raise ValueError("SEC API key not found in config or environment")
        
        # Initialize SEC API clients
        self.query_api = QueryApi(api_key=self.api_key)
        self.extractor_api = ExtractorApi(api_key=self.api_key)
        
        # Load sections config
        self.sections_config = config.sections_config
        
        # Load date range from config - with fallback defaults
        # Default to last 2 years if not specified
        default_start = (datetime.now().replace(year=datetime.now().year - 2)).strftime("%Y-%m-%d")
        default_end = datetime.now().strftime("%Y-%m-%d")
        
        self.start_date = getattr(config.api, 'sec_fetch_start_date', default_start)
        self.end_date = getattr(config.api, 'sec_fetch_end_date', None) or default_end
        
        # Caching
        self._query_cache = {}  # Cache query results
        self._section_cache = {}  # Cache extracted sections
        
        logger.info(
            f"SECFetcher initialized - Date range: {self.start_date} to {self.end_date}"
        )
        
        # Validate API key
        self._validate_api_key()
    
    def _validate_api_key(self) -> bool:
        """
        Validate API key by making a test query
        
        Returns:
            True if valid
            
        Raises:
            ValueError: If API key is invalid
        """
        try:
            logger.info("🔑 Validating SEC API key...")
            
            # Simple test query
            test_query = {
                "query": "ticker:AAPL AND formType:\"10-K\"",
                "from": "0",
                "size": "1"
            }
            
            result = self.query_api.get_filings(test_query)
            
            if result and 'filings' in result:
                logger.info("✅ API key validated successfully")
                return True
            else:
                raise ValueError("Invalid API response structure")
                
        except Exception as e:
            logger.error(f"❌ API key validation failed: {e}")
            raise ValueError(f"Invalid SEC API key: {e}")
    
    def query_filings(
        self,
        ticker: str,
        filing_types: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query SEC API for filings with caching and pagination
        
        Args:
            ticker: Company ticker symbol
            filing_types: List of filing types (default: ['10-K', '10-Q'])
            start_date: Start date YYYY-MM-DD (default: from config)
            end_date: End date YYYY-MM-DD (default: from config)
            
        Returns:
            List of filing metadata dictionaries sorted by filing date (newest first)
        """
        filing_types = filing_types or ['10-K', '10-Q']
        start_date = start_date or self.start_date
        end_date = end_date or self.end_date
        
        # Check cache first
        cache_key = f"{ticker}_{'-'.join(sorted(filing_types))}_{start_date}_{end_date}"
        if cache_key in self._query_cache:
            logger.info(f"📦 Using cached query results for {ticker}")
            return self._query_cache[cache_key]
        
        logger.info(f"🔍 Querying SEC filings for {ticker} ({start_date} to {end_date})")
        
        all_filings = []
        
        # Build Lucene query
        form_types_query = " OR ".join([f'formType:"{ft}"' for ft in filing_types])
        query_string = (
            f'ticker:{ticker} AND ({form_types_query}) '
            f'AND filedAt:[{start_date} TO {end_date}]'
        )
        
        logger.debug(f"Query string: {query_string}")
        
        # Pagination - use defaults with fallback
        from_index = 0
        page_size = getattr(config.api, 'sec_max_results_per_query', 50)
        page_number = 1
        fetch_all_pages = getattr(config.api, 'sec_fetch_all_pages', True)
        
        while True:
            query_payload = {
                "query": query_string,
                "from": str(from_index),
                "size": str(page_size),
                "sort": [{"filedAt": {"order": "desc"}}]
            }
            
            # Wait for rate limit
            self._wait_for_rate_limit()
            
            try:
                # Execute query
                response = self.query_api.get_filings(query_payload)
                filings = response.get('filings', [])
                
                if not filings:
                    logger.info(f"  No more filings found (page {page_number})")
                    break
                
                all_filings.extend(filings)
                logger.info(f"  Page {page_number}: Retrieved {len(filings)} filings")
                
                # Check if more pages exist
                total_available = response.get('total', {}).get('value', 0)
                logger.debug(f"  Total available: {total_available}, Retrieved so far: {len(all_filings)}")
                
                # Stop if we've got everything
                if len(all_filings) >= total_available:
                    break
                
                # Stop if not fetching all pages
                if not fetch_all_pages:
                    logger.warning("fetch_all_pages is False, stopping after first page")
                    break
                
                # Move to next page
                from_index += page_size
                page_number += 1
                
            except Exception as e:
                logger.error(f"❌ Error querying filings (page {page_number}): {e}")
                break
        
        logger.info(f"✅ Query complete: Found {len(all_filings)} total filings for {ticker}")
        
        # Cache results
        self._query_cache[cache_key] = all_filings
        
        return all_filings
    
    def extract_section(
        self,
        filing_url: str,
        section_code: str,
        filing_accession: str,
        return_type: str = "text"
    ) -> Optional[str]:
        """
        Extract a specific section from a filing with retry logic
        
        Args:
            filing_url: URL to filing
            section_code: Section to extract (e.g., '1A', 'part1item1')
            filing_accession: Accession number for caching
            return_type: 'text' or 'html'
            
        Returns:
            Extracted section text or None if extraction fails
        """
        # Check cache first
        cache_key = hashlib.md5(
            f"{filing_accession}_{section_code}".encode()
        ).hexdigest()
        
        if cache_key in self._section_cache:
            logger.debug(f"📦 Cache hit for section {section_code}")
            return self._section_cache[cache_key]
        
        # Get retry settings from config
        max_retries = self.sections_config['extraction']['max_retries']
        retry_delay = self.sections_config['extraction']['retry_delay']
        
        # Extract with retry logic
        for attempt in range(1, max_retries + 1):
            try:
                # Wait for rate limit
                self._wait_for_rate_limit()
                
                # Extract section
                section_text = self.extractor_api.get_section(
                    filing_url,
                    section_code,
                    return_type
                )
                
                # Check if "processing" status (section might not exist)
                if section_text and isinstance(section_text, str):
                    lower_text = section_text.lower()
                    if "processing" in lower_text and len(section_text) < 100:
                        if attempt < max_retries:
                            logger.warning(
                                f"⏳ Section {section_code} still processing, "
                                f"retry {attempt}/{max_retries}"
                            )
                            time.sleep(retry_delay)
                            continue
                        else:
                            logger.warning(
                                f"⚠️  Section {section_code} not available after "
                                f"{max_retries} retries"
                            )
                            return None
                
                # Validate extracted text
                if self._validate_section_text(section_text, section_code):
                    # Cache successful extraction
                    self._section_cache[cache_key] = section_text
                    logger.debug(
                        f"✅ Extracted section {section_code} ({len(section_text):,} chars)"
                    )
                    return section_text
                else:
                    logger.warning(f"⚠️  Section {section_code} validation failed")
                    return None
                    
            except Exception as e:
                logger.error(f"❌ Error extracting section {section_code} (attempt {attempt}): {e}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    return None
        
        return None
    
    def _validate_section_text(self, text: str, section_code: str) -> bool:
        """
        Validate extracted section text
        
        Args:
            text: Extracted text
            section_code: Section code
            
        Returns:
            True if valid, False otherwise
        """
        if not text or not isinstance(text, str):
            logger.debug(f"Section {section_code}: Empty or invalid type")
            return False
        
        # Minimum length check (100 chars)
        if len(text) < 100:
            logger.debug(f"Section {section_code}: Too short ({len(text)} chars)")
            return False
        
        # Check for common error patterns in first 200 chars
        error_patterns = [
            "not available",
            "error occurred",
            "failed to extract",
            "unable to process"
        ]
        
        lower_text = text.lower()[:200]
        for pattern in error_patterns:
            if pattern in lower_text:
                logger.debug(f"Section {section_code}: Contains error pattern '{pattern}'")
                return False
        
        return True
    
    def get_section_codes(self, filing_type: str) -> Dict[str, str]:
        """
        Get section codes and names for a filing type
        
        Args:
            filing_type: '10-K' or '10-Q'
            
        Returns:
            Dictionary mapping section codes to names
        """
        sections = self.sections_config['sec_filing_sections'].get(filing_type, {})
        
        if not sections:
            logger.error(f"No section configuration found for filing type: {filing_type}")
            return {}
        
        return sections
    
    def fetch_filings_with_sections(
        self,
        ticker: str,
        filing_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Complete workflow: Query filings + Extract all sections
        
        Args:
            ticker: Company ticker symbol
            filing_types: Filing types to fetch (default: ['10-K', '10-Q'])
            
        Returns:
            List of successfully extracted filings with sections
            
        Behavior:
            - STRICT MODE: Skips entire filing if any section fails
            - Logs detailed errors for debugging
            - Returns only successfully extracted filings
        """
        filing_types = filing_types or ['10-K', '10-Q']
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📥 STARTING FETCH FOR {ticker}")
        logger.info(f"{'='*70}")
        
        # Step 1: Query all available filings
        filings = self.query_filings(ticker, filing_types)
        
        if not filings:
            logger.warning(f"No filings found for {ticker}")
            return []
        
        logger.info(f"Found {len(filings)} filings to process")
        
        # Step 2: Extract sections from each filing
        results = []
        skipped_filings = []
        
        for i, filing in enumerate(filings, 1):
            filing_type = filing['formType']
            filing_url = filing['linkToFilingDetails']
            accession_no = filing['accessionNo']
            filed_at = filing['filedAt']
            filing_date = filed_at.split('T')[0] if 'T' in filed_at else filed_at
            
            logger.info(
                f"\n[{i}/{len(filings)}] Processing {filing_type} "
                f"filed {filing_date} | Accession: {accession_no}"
            )
            
            # Get section codes for this filing type
            section_codes = self.get_section_codes(filing_type)
            
            if not section_codes:
                logger.error(f"  ❌ No sections configured for {filing_type}, skipping")
                skipped_filings.append({
                    'accession': accession_no,
                    'reason': 'No section configuration'
                })
                continue
            
            # Extract all sections
            start_time = time.time()
            extracted_sections = {}
            failed_sections = []
            
            for section_code, section_name in section_codes.items():
                logger.info(f"  📄 Extracting section {section_code} ({section_name})...")
                
                section_text = self.extract_section(
                    filing_url=filing_url,
                    section_code=section_code,
                    filing_accession=accession_no,
                    return_type=self.sections_config['extraction']['return_type']
                )
                
                if section_text:
                    extracted_sections[section_code] = section_text
                    logger.info(f"     ✅ Success ({len(section_text):,} characters)")
                else:
                    failed_sections.append(section_code)
                    logger.error(f"     ❌ FAILED to extract section {section_code}")
            
            extraction_time = time.time() - start_time
            
            # STRICT MODE: Skip filing if any section failed
            error_mode = self.sections_config['error_handling']['mode']
            if error_mode == "strict" and failed_sections:
                logger.error(
                    f"\n  ❌ FILING SKIPPED (STRICT MODE): {filing_type} ({accession_no})\n"
                    f"     Failed sections: {', '.join(failed_sections)}\n"
                    f"     Extracted: {len(extracted_sections)}/{len(section_codes)}"
                )
                skipped_filings.append({
                    'accession': accession_no,
                    'filing_type': filing_type,
                    'filing_date': filing_date,
                    'reason': f'Failed sections: {failed_sections}'
                })
                continue
            
            # Build filing metadata
            filing_metadata = {
                'ticker': ticker,
                'filing_type': filing_type,
                'filing_date': filing_date,
                'accession_number': accession_no,
                'filing_url': filing_url,
                'company_name': filing['companyName'],
                'cik': filing['cik'],
                'fiscal_year': self._extract_fiscal_year(filing),
                'fiscal_quarter': self._extract_fiscal_quarter(filing, filing_type),
                'period_of_report': filing.get('periodOfReport', filing_date)
            }
            
            # Build extraction stats
            extraction_stats = {
                'total_sections_expected': len(section_codes),
                'sections_extracted': len(extracted_sections),
                'sections_failed': len(failed_sections),
                'failed_section_codes': failed_sections,
                'extraction_time_seconds': round(extraction_time, 2),
                'success': len(failed_sections) == 0
            }
            
            # Add to results
            result = {
                'filing_metadata': filing_metadata,
                'sections': extracted_sections,
                'extraction_stats': extraction_stats
            }
            
            results.append(result)
            
            logger.info(
                f"  ✅ Filing complete: {len(extracted_sections)}/{len(section_codes)} "
                f"sections in {extraction_time:.2f}s"
            )
        
        # Print summary
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 SUMMARY FOR {ticker}")
        logger.info(f"{'='*70}")
        logger.info(f"Total filings found:        {len(filings)}")
        logger.info(f"Successfully processed:     {len(results)}")
        logger.info(f"Skipped (failed sections):  {len(skipped_filings)}")
        
        if skipped_filings:
            logger.warning(f"\n⚠️  SKIPPED FILINGS:")
            for skipped in skipped_filings:
                logger.warning(
                    f"  - {skipped.get('filing_type', 'N/A')} | "
                    f"{skipped.get('filing_date', 'N/A')} | "
                    f"{skipped['accession']} | Reason: {skipped['reason']}"
                )
        
        logger.info(f"{'='*70}\n")
        
        return results
    
    def _extract_fiscal_year(self, filing: Dict) -> Optional[int]:
        """
        Extract fiscal year from filing metadata
        
        Args:
            filing: Filing metadata from Query API
            
        Returns:
            Fiscal year as integer
        """
        try:
            # Try periodOfReport first, fallback to filedAt
            period = filing.get('periodOfReport') or filing.get('filedAt')
            if period:
                return int(period[:4])
        except (ValueError, TypeError, IndexError):
            pass
        
        return None
    
    def _extract_fiscal_quarter(
        self,
        filing: Dict,
        filing_type: str
    ) -> Optional[int]:
        """
        Extract fiscal quarter from filing metadata
        
        Args:
            filing: Filing metadata
            filing_type: Filing type
            
        Returns:
            1, 2, or 3 for 10-Q filings (Q4 is in 10-K)
            None for 10-K filings
        """
        if filing_type != '10-Q':
            return None
        
        try:
            period = filing.get('periodOfReport')
            if not period:
                return None
            
            # Parse month from date (YYYY-MM-DD format)
            month = int(period[5:7])
            
            # Determine quarter from month
            # Q1: Jan-Mar (months 1-3)
            # Q2: Apr-Jun (months 4-6)
            # Q3: Jul-Sep (months 7-9)
            # Q4: Oct-Dec (10-12) - should be in 10-K
            if 1 <= month <= 3:
                return 1
            elif 4 <= month <= 6:
                return 2
            elif 7 <= month <= 9:
                return 3
            else:
                # Q4 should be in 10-K, not 10-Q
                logger.warning(
                    f"Unexpected Q4 period in 10-Q: {period}"
                )
                return None
        
        except (ValueError, TypeError, IndexError):
            logger.warning(f"Could not extract quarter from period: {filing.get('periodOfReport')}")
            return None
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache sizes
        """
        return {
            'query_cache_entries': len(self._query_cache),
            'section_cache_entries': len(self._section_cache)
        }
    
    def clear_cache(self, cache_type: Optional[str] = None):
        """
        Clear caches
        
        Args:
            cache_type: 'query', 'section', or None (clear both)
        """
        if cache_type == 'query' or cache_type is None:
            self._query_cache.clear()
            logger.info("🗑️  Cleared query cache")
        
        if cache_type == 'section' or cache_type is None:
            self._section_cache.clear()
            logger.info("🗑️  Cleared section cache")
    
    def fetch(self, *args, **kwargs):
        """
        Implementation of abstract fetch() method from BaseFetcher
        
        Delegates to fetch_filings_with_sections()
        """
        return self.fetch_filings_with_sections(*args, **kwargs)


# ==================== STANDALONE TEST ====================

if __name__ == "__main__":
    """
    Test SEC fetcher with one company
    
    Usage:
        python src/data_ingestion/sec_fetcher.py
    """
    
    print("\n" + "="*70)
    print("TESTING SEC FETCHER")
    print("="*70 + "\n")
    
    try:
        # Initialize fetcher
        fetcher = SECFetcher()
        
        # Test with Apple (well-structured filings)
        test_ticker = "AAPL"
        
        print(f"Testing with {test_ticker}...\n")
        
        # Fetch filings
        results = fetcher.fetch_filings_with_sections(test_ticker)
        
        # Display results
        print(f"\n{'='*70}")
        print(f"RESULTS")
        print(f"{'='*70}\n")
        
        if results:
            print(f"✅ Successfully fetched {len(results)} filings\n")
            
            for i, result in enumerate(results, 1):
                meta = result['filing_metadata']
                sections = result['sections']
                stats = result['extraction_stats']
                
                print(f"{i}. {meta['filing_type']} | {meta['filing_date']} | {meta['accession_number']}")
                print(f"   Company: {meta['company_name']}")
                print(f"   Sections: {stats['sections_extracted']}/{stats['total_sections_expected']}")
                print(f"   Time: {stats['extraction_time_seconds']}s")
                
                # Show section sizes
                for section_code, section_text in sections.items():
                    section_name = fetcher.get_section_codes(meta['filing_type']).get(section_code, section_code)
                    print(f"     - {section_code} ({section_name}): {len(section_text):,} chars")
                print()
        else:
            print("❌ No filings were successfully extracted")
        
        # Show cache stats
        cache_stats = fetcher.get_cache_stats()
        print(f"Cache Statistics:")
        print(f"  Query cache: {cache_stats['query_cache_entries']} entries")
        print(f"  Section cache: {cache_stats['section_cache_entries']} entries")
        
        print(f"\n{'='*70}")
        print("✅ TEST COMPLETE")
        print(f"{'='*70}\n")
        
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\n💡 Make sure to:")
        print("   1. Set SEC_API_KEY in your .env file")
        print("   2. Update configs/dev.yaml with API configuration")
        print("   3. Create configs/sections_config.yaml")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()