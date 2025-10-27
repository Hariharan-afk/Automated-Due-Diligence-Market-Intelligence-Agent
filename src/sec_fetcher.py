"""
SEC EDGAR filing fetcher with hybrid URL+API approach.
Uses free SEC URLs for metadata and paid API only for section extraction.
Implements caching to avoid redundant API calls.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

# Try relative imports first (package), fall back to absolute (script)
try:
    from .utils.logger import get_logger
    from .utils.config import get_config
    logger = get_logger("sec_fetcher")
except ImportError:
    # Fallback for standalone execution
    logger = logging.getLogger("sec_fetcher")
    def get_config():
        """Fallback config loader"""
        import yaml
        import os
        config_path = "config/config.yaml"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        return {}


@dataclass
class FilingMetadata:
    """Metadata for a SEC filing."""
    ticker: str
    company_name: str
    cik: str
    filing_type: str  # 10-K, 10-Q, 8-K
    filing_date: str
    fiscal_year: int
    fiscal_period: str  # FY, Q1, Q2, Q3, Q4
    accession_number: str
    filing_url: str


@dataclass
class FilingContent:
    """Structured content from a SEC filing."""
    metadata: FilingMetadata
    sections: Dict[str, str]  # section_name -> text content
    tables: List[Dict[str, Any]]  # Financial tables
    raw_text: str  # Full filing text
    extraction_date: str


class SECFetcher:
    """
    Fetches SEC filings using hybrid URL+API approach to minimize costs.

    Strategy:
    1. Use free SEC URLs for ticker lookup and filing lists
    2. Check local database cache before fetching
    3. Use paid API only for extracting sections/tables from new filings
    """

    # Free SEC EDGAR URLs
    SEC_EDGAR_BASE = "https://data.sec.gov"
    SEC_EDGAR_ARCHIVE = "https://www.sec.gov/cgi-bin/browse-edgar"

    # Paid API URL
    SEC_API_BASE = "https://api.sec-api.io"

    def __init__(self, api_key: Optional[str] = None, use_cache: bool = True):
        """
        Initialize SEC fetcher with hybrid approach.

        Args:
            api_key: sec-api.io API key (if None, reads from config)
            use_cache: Whether to check cache before fetching
        """
        self.config = get_config()

        # Handle both dict and object-style config access
        import os
        if isinstance(self.config, dict):
            self.api_key = api_key or os.getenv('SEC_API_KEY') or self.config.get('sec_api_key', '')
            sec_api_config = self.config.get('sec_api', {})
            cache_enabled = sec_api_config.get('cache_enabled', True)
            rate_limit_config = sec_api_config.get('rate_limit', {})
            self.rate_limit = rate_limit_config.get('calls_per_minute', 10)
        else:
            self.api_key = api_key or self.config.sec_api_key
            cache_enabled = self.config.sec_api.cache_enabled
            self.rate_limit = self.config.sec_api.rate_limit.calls_per_minute

        self.use_cache = use_cache and cache_enabled

        # Session for requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "CompanyResearchPipeline/1.0 (research@example.com)"
        })

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 60.0 / self.rate_limit

        # Load company tickers
        self.company_tickers = self._load_company_tickers()

        logger.info(f"SEC Fetcher initialized (cache: {self.use_cache})")

    def _load_company_tickers(self) -> Dict[str, Dict]:
        """Load company tickers from local JSON file."""
        # Handle both dict and object-style config access
        if isinstance(self.config, dict):
            ticker_config = self.config.get('ticker_file', {})
            ticker_path = ticker_config.get('path', 'data/company_tickers.json') if isinstance(ticker_config, dict) else 'data/company_tickers.json'
        else:
            ticker_path = self.config.ticker_file.get("path", "data/company_tickers.json")

        ticker_file = Path(ticker_path)

        if not ticker_file.exists():
            logger.warning(f"Ticker file not found: {ticker_file}")
            return {}

        try:
            with open(ticker_file, 'r') as f:
                data = json.load(f)

            # Convert to dictionary for easy lookup
            # Format: {ticker: {cik, title, ticker}, ...}
            tickers = {}
            for key, value in data.items():
                if isinstance(value, dict):
                    ticker = value.get('ticker', '')
                    if ticker:
                        tickers[ticker.upper()] = value

            logger.info(f"Loaded {len(tickers)} company tickers")
            return tickers

        except Exception as e:
            logger.error(f"Failed to load ticker file: {e}")
            return {}

    def _rate_limit(self):
        """Enforce rate limiting between API calls."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def get_company_cik(self, ticker: str) -> Optional[str]:
        """
        Get CIK number for a company ticker using local data.

        Args:
            ticker: Company ticker symbol

        Returns:
            CIK number or None if not found
        """
        ticker = ticker.upper()

        if ticker in self.company_tickers:
            cik_str = str(self.company_tickers[ticker].get('cik_str', ''))
            # Pad CIK to 10 digits
            cik = cik_str.zfill(10)
            logger.info(f"Found CIK {cik} for ticker {ticker}")
            return cik

        logger.warning(f"CIK not found for ticker: {ticker}")
        return None

    def get_company_name(self, ticker: str) -> Optional[str]:
        """Get company name for a ticker."""
        ticker = ticker.upper()

        if ticker in self.company_tickers:
            return self.company_tickers[ticker].get('title', '')

        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((requests.RequestException, TimeoutError))
    )
    def _fetch_free_url(self, url: str, params: Optional[Dict] = None) -> requests.Response:
        """
        Fetch data from free SEC URL with retry logic.

        Args:
            url: URL to fetch
            params: Query parameters

        Returns:
            Response object
        """
        # Rate limit to be respectful to SEC servers
        self._rate_limit()

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response
        except requests.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning("Rate limit exceeded on free API, backing off...")
                time.sleep(5)
                raise
            logger.error(f"HTTP error on free API: {e}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

    def get_filings_list_free(
        self,
        cik: str,
        filing_types: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get list of filings using free SEC submissions API.

        Args:
            cik: Company CIK (10-digit padded)
            filing_types: List of filing types (e.g., ["10-K", "10-Q"])
            start_date: Start date filter
            end_date: End date filter

        Returns:
            List of filing metadata dicts
        """
        try:
            # Use SEC submissions API (free)
            # CIK must be zero-padded to 10 digits
            cik_padded = str(cik).zfill(10)
            url = f"{self.SEC_EDGAR_BASE}/submissions/CIK{cik_padded}.json"

            logger.debug(f"Fetching filings list from free API: {url}")
            response = self._fetch_free_url(url)
            data = response.json()

            # Extract filings from recent section
            filings = []
            recent_filings = data.get("filings", {}).get("recent", {})

            if not recent_filings:
                logger.warning(f"No recent filings found for CIK {cik}")
                return []

            # Parse filings
            forms = recent_filings.get("form", [])
            filing_dates = recent_filings.get("filingDate", [])
            accession_numbers = recent_filings.get("accessionNumber", [])
            primary_documents = recent_filings.get("primaryDocument", [])

            for i in range(len(forms)):
                form = forms[i]

                # Filter by filing type
                if form not in filing_types:
                    continue

                filing_date_str = filing_dates[i]
                filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d")

                # Filter by date range
                if start_date and filing_date < start_date:
                    continue
                if end_date and filing_date > end_date:
                    continue

                # Build filing URL
                accession_no = accession_numbers[i].replace("-", "")
                primary_doc = primary_documents[i]
                filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no}/{primary_doc}"

                filings.append({
                    "formType": form,
                    "filedAt": filing_date_str,
                    "accessionNo": accession_numbers[i],
                    "primaryDocument": primary_doc,
                    "linkToFilingDetails": filing_url
                })

            logger.info(f"Found {len(filings)} filings for CIK {cik} using free API")
            return filings

        except Exception as e:
            logger.error(f"Failed to fetch filings list for CIK {cik}: {e}")
            return []

    def is_filing_cached(self, accession_number: str) -> bool:
        """
        Check if filing is already in database cache.

        Args:
            accession_number: SEC accession number

        Returns:
            True if cached, False otherwise
        """
        if not self.use_cache:
            return False

        try:
            from .db_manager import is_filing_cached
            return is_filing_cached(accession_number, self.config.database_path)
        except Exception as e:
            logger.warning(f"Error checking cache: {e}")
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((requests.RequestException, TimeoutError))
    )
    def extract_filing_sections_api(
        self,
        filing_url: str,
        filing_type: str
    ) -> Dict[str, str]:
        """
        Extract sections using PAID sec-api.io Extractor API.
        Only call this for NEW filings not in cache!

        Args:
            filing_url: URL to the SEC filing
            filing_type: Type of filing (10-K or 10-Q)

        Returns:
            Dictionary of section_name -> text content
        """
        if not self.api_key or self.api_key == "your_sec_api_key_here":
            logger.error("SEC API key not configured! Cannot extract sections.")
            return {}

        try:
            sections = {}

            # Define sections based on filing type
            # Handle both dict and object-style config access
            if isinstance(self.config, dict):
                sec_api_config = self.config.get('sec_api', {})
                filings_config = sec_api_config.get('filings', {})
                sections_to_extract = filings_config.get('sections_to_extract', {})
                sections_config = sections_to_extract.get(filing_type, [])
            else:
                sections_config = self.config.sec_api.filings.sections_to_extract.get(filing_type, [])

            if filing_type == "10-K":
                section_names = {
                    "1": "Business",
                    "1A": "Risk Factors",
                    "7": "MD&A",
                    "8": "Financial Statements"
                }
            elif filing_type == "10-Q":
                section_names = {
                    "part1item1": "Financial Statements",
                    "part1item2": "MD&A",
                    "part2item1a": "Risk Factors"
                }
            else:
                logger.warning(f"Unsupported filing type for extraction: {filing_type}")
                return {}

            # Extract each section using PAID API
            endpoint = f"{self.SEC_API_BASE}/extractor"

            for item_code in sections_config:
                item_name = section_names.get(item_code, item_code)

                try:
                    params = {
                        "url": filing_url,
                        "item": item_code,
                        "type": "text",
                        "token": self.api_key
                    }

                    self._rate_limit()
                    logger.debug(f"Extracting {item_name} using PAID API")

                    response = self.session.get(endpoint, params=params, timeout=60)

                    if response.status_code == 200:
                        sections[item_name] = response.text
                        logger.info(f"Extracted {item_name} ({len(response.text)} chars)")
                    else:
                        logger.warning(f"Could not extract {item_name}: {response.status_code}")

                except Exception as e:
                    logger.warning(f"Failed to extract {item_name}: {e}")
                    continue

            logger.info(f"Extracted {len(sections)} sections using PAID API")
            return sections

        except Exception as e:
            logger.error(f"Failed to extract sections from filing: {e}")
            return {}

    def fetch_filing(
        self,
        ticker: str,
        filing_type: str,
        company_name: str = "",
        cik: str = "",
        year: Optional[int] = None
    ) -> Optional[FilingContent]:
        """
        Fetch SEC filing with intelligent caching.

        Strategy:
        1. Get CIK from local ticker data
        2. Get filing list using free API
        3. Check if filing is cached
        4. Extract sections using PAID API only if not cached

        Args:
            ticker: Company ticker
            filing_type: Type of filing (10-K, 10-Q)
            company_name: Company name (optional)
            cik: CIK number (optional, will lookup if not provided)
            year: Specific year to fetch (optional)

        Returns:
            FilingContent object or None if not found
        """
        try:
            # Get CIK if not provided
            if not cik:
                cik = self.get_company_cik(ticker)
                if not cik:
                    logger.error(f"Could not find CIK for ticker: {ticker}")
                    return None

            # Get company name if not provided
            if not company_name:
                company_name = self.get_company_name(ticker) or ""

            # Determine date range
            # Handle both dict and object-style config access
            if isinstance(self.config, dict):
                sec_api_config = self.config.get('sec_api', {})
                filings_config = sec_api_config.get('filings', {})
                years_to_fetch = filings_config.get('years_to_fetch', 3)
            else:
                years_to_fetch = self.config.sec_api.filings.years_to_fetch

            end_date = datetime.now()
            start_date = end_date - timedelta(days=365 * years_to_fetch)

            if year:
                start_date = datetime(year, 1, 1)
                end_date = datetime(year, 12, 31)

            # Get filing list using FREE API
            logger.info(f"Fetching {filing_type} list for {ticker} ({cik}) using FREE API")
            filings = self.get_filings_list_free(cik, [filing_type], start_date, end_date)

            if not filings:
                logger.warning(f"No {filing_type} filings found for {ticker}")
                return None

            # Get most recent filing
            latest_filing = filings[0]
            accession_number = latest_filing.get("accessionNo")
            filing_url = latest_filing.get("linkToFilingDetails")
            filing_date = latest_filing.get("filedAt", "")

            logger.info(f"Latest {filing_type}: {accession_number} filed on {filing_date}")

            # Check if cached
            if self.is_filing_cached(accession_number):
                logger.info(f"Filing {accession_number} found in cache, skipping extraction")
                # TODO: Load from database
                return None

            # Extract sections using PAID API (only for new filings)
            logger.info(f"Filing {accession_number} not cached, extracting using PAID API")
            sections = self.extract_filing_sections_api(filing_url, filing_type)

            if not sections:
                logger.warning(f"No sections extracted for {accession_number}")

            # Create metadata
            metadata = FilingMetadata(
                ticker=ticker,
                company_name=company_name,
                cik=cik,
                filing_type=filing_type,
                filing_date=filing_date,
                fiscal_year=int(filing_date[:4]) if filing_date else 0,
                fiscal_period=filing_date,
                accession_number=accession_number,
                filing_url=filing_url
            )

            # Create filing content
            content = FilingContent(
                metadata=metadata,
                sections=sections,
                tables=[],  # TODO: Extract tables in future
                raw_text="",
                extraction_date=datetime.now().isoformat()
            )

            logger.info(f"Successfully fetched {filing_type} for {ticker}")
            return content

        except Exception as e:
            logger.error(f"Failed to fetch {filing_type} for {ticker}: {e}")
            return None

    def save_filing(self, filing: FilingContent, output_dir: Path):
        """
        Save filing to disk.

        Args:
            filing: FilingContent object
            output_dir: Output directory
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            # Clean filename
            filing_date_clean = filing.metadata.filing_date.replace(":", "-").replace("T", "_")
            filename = f"{filing.metadata.ticker}_{filing.metadata.filing_type}_{filing_date_clean}.json"
            filepath = output_dir / filename

            # Convert to dict for JSON serialization
            data = {
                "metadata": asdict(filing.metadata),
                "sections": filing.sections,
                "tables": filing.tables,
                "raw_text": filing.raw_text,
                "extraction_date": filing.extraction_date
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved filing to {filepath}")

        except Exception as e:
            logger.error(f"Failed to save filing: {e}")


# Example usage
if __name__ == "__main__":
    fetcher = SECFetcher()

    # Fetch Apple's latest 10-K (will check cache first)
    filing = fetcher.fetch_filing(
        ticker="AAPL",
        filing_type="10-K"
    )

    if filing:
        print(f"Fetched {filing.metadata.filing_type} dated {filing.metadata.filing_date}")
        print(f"Sections: {list(filing.sections.keys())}")
        print(f"Cached sections length: {sum(len(v) for v in filing.sections.values())} characters")

        # Save to disk
        output_dir = Path("data/raw/sec_filings")
        fetcher.save_filing(filing, output_dir)
