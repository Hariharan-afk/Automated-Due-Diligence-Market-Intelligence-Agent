# researcher_agent/src/data_fetcher.py
import json
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sec_api import QueryApi, ExtractorApi
from groq import Groq

from utils.config import config


class SECDataFetcher:
    """Handles fetching and extracting data from SEC filings"""
    
    def __init__(self):
        self.query_api = QueryApi(api_key=config.SEC_API_KEY)
        self.extractor_api = ExtractorApi(api_key=config.SEC_API_KEY)
        self.rate_limit_delay = 1.0 / config.SEC_API_RATE_LIMIT  # seconds between requests

    def _convert_time_horizon_to_dates(self, time_horizon: str) -> tuple[str, str]:
        """
        Convert time_horizon string to start and end dates
        
        Args:
            time_horizon: One of "current_year", "last_3_years", "last_5_years", "custom"
            
        Returns:
            Tuple of (start_date, end_date) in format "YYYY-MM-DD"
        """
        end_date = datetime.now()
        
        horizon_map = {
            "current_year": timedelta(days=365),
            "last_3_years": timedelta(days=3*365),
            "last_5_years": timedelta(days=5*365)
        }
        
        time_delta = horizon_map.get(time_horizon, timedelta(days=365))
        start_date = end_date - time_delta
        
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
    
    def fetch_sec_filings(
        self, 
        ticker: str, 
        time_horizon: str = "current_year",
        filing_types: List[str] = None,
        max_filings: int = 100
    ) -> List[Dict]:
        """
        Fetch multiple filings of specified types within a timeline
        
        Args:
            ticker: Company ticker symbol
            time_horizon: Time period to search ("current_year", "last_3_years", "last_5_years")
            filing_types: List of filing types to fetch (default: ["10-K", "10-Q"])
            max_filings: Maximum number of filings to return
            
        Returns:
            List of filing metadata dictionaries
        """
        if filing_types is None:
            filing_types = ["10-K", "10-Q"]
        
        try:
            # Convert time horizon to dates
            start_date, end_date = self._convert_time_horizon_to_dates(time_horizon)
            
            # Build form types query string
            form_types_query = " OR ".join([f'formType:"{ft}"' for ft in filing_types])
            
            # Construct query
            query = {
                "query": f'ticker:{ticker} AND ({form_types_query}) AND filedAt:[{start_date} TO {end_date}]',
                "from": "0",
                "size": str(max_filings),
                "sort": [{"filedAt": {"order": "desc"}}]
            }
            
            print(f"\nSearching for {', '.join(filing_types)} filings for {ticker}")
            print(f"Date range: {start_date} to {end_date}")
            
            response = self.query_api.get_filings(query)
            
            filings = response.get('filings', [])
            
            if not filings:
                print(f"✗ No filings found for {ticker} in specified timeline")
                return []
            
            print(f"✓ Found {len(filings)} filing(s)")
            
            # Print summary
            for filing in filings:
                print(f"  - {filing['formType']:6s} | {filing['filedAt']} | {filing['companyName']}")
            
            return filings
            
        except Exception as e:
            print(f"✗ Error fetching filings: {e}")
            return []

    
    def extract_sections(
        self, 
        filing_url: str, 
        filing_type: str
    ) -> Dict[str, str]:
        """
        Extract specific sections from a filing in TEXT format
        
        Args:
            filing_url: URL to the filing
            filing_type: Type of filing (determines which sections to extract)
            
        Returns:
            Dictionary mapping section codes to extracted text content
        """
        # Define sections to extract based on filing type
        sections_map = {
            '10-K': {
                '1': 'Business',
                '1A': 'Risk Factors',
                '7': 'Management Discussion and Analysis',
                '8': 'Financial Statements'
            },
            '10-Q': {
                'part1item1': 'Financial Statements',
                'part1item2': 'Management Discussion and Analysis',
                'part2item1a': 'Risk Factors'
            }
        }
        
        sections_to_extract = sections_map.get(filing_type, {})
        extracted_sections = {}
        
        for section_code, section_name in sections_to_extract.items():
            try:
                # Rate limiting
                time.sleep(self.rate_limit_delay)
                
                # Extract section as TEXT (includes ##TABLE_START/END markers)
                section_text = self.extractor_api.get_section(
                    filing_url,
                    section_code,
                    return_type="text"
                )
                
                extracted_sections[section_code] = section_text
                
                print(f"✓ Extracted Section {section_code} ({section_name}): "
                      f"{len(section_text):,} characters")
                
            except Exception as e:
                print(f"✗ Failed to extract Section {section_code} ({section_name}): {e}")
                continue
        
        return extracted_sections
    
    # def fetch_filing_with_sections(
    #     self, 
    #     ticker: str, 
    #     filing_type: str = "10-K"
    # ) -> Optional[Dict]:
    #     """
    #     Complete workflow: Fetch filing metadata and extract all sections
        
    #     Args:
    #         ticker: Company ticker symbol
    #         filing_type: Type of filing
            
    #     Returns:
    #         Dictionary containing filing metadata and extracted sections
    #     """
    #     # Step 1: Get filing metadata
    #     filing_metadata = self.fetch_latest_filing(ticker, filing_type)
        
    #     if not filing_metadata:
    #         return None
        
    #     # Step 2: Extract sections
    #     print(f"\nExtracting sections from {filing_type}...")
    #     sections = self.extract_sections(
    #         filing_metadata['linkToFilingDetails'],
    #         filing_type
    #     )
        
    #     if not sections:
    #         print(f"✗ No sections could be extracted from {filing_type}")
    #         return None
        
    #     return {
    #         'filing_metadata': filing_metadata,
    #         'sections': sections
    #     }
    
    
    def fetch_filings_with_sections(
        self,
        ticker: str,
        time_horizon: str = "current_year",
        filing_types: List[str] = None,
        max_filings: int = 10,
        extract_sections: bool = True
    ) -> List[Dict]:
        """
        Fetch multiple filings within a timeline and optionally extract sections
        
        Args:
            ticker: Company ticker symbol
            time_horizon: Time period to search
            filing_types: List of filing types to fetch
            max_filings: Maximum number of filings to process
            extract_sections: Whether to extract sections (can be slow for many filings)
            
        Returns:
            List of dictionaries containing filing metadata and extracted sections
        """
        # Step 1: Get all filings in timeline
        filings = self.fetch_sec_filings(
            ticker=ticker,
            time_horizon=time_horizon,
            filing_types=filing_types,
            max_filings=max_filings
        )
        
        if not filings:
            return []
        
        results = []
        
        # Step 2: Process each filing
        for i, filing in enumerate(filings, 1):
            filing_type = filing['formType']
            print(f"\n[{i}/{len(filings)}] Processing {filing_type} filed on {filing['filedAt']}")
            
            result = {
                'filing_metadata': filing,
                'sections': {}
            }
            
            # Step 3: Extract sections if requested
            if extract_sections:
                try:
                    sections = self.extract_sections(
                        filing['linkToFilingDetails'],
                        filing_type
                    )
                    result['sections'] = sections
                except Exception as e:
                    print(f"✗ Error extracting sections: {e}")
            
            results.append(result)
            
            # Rate limiting between filings
            if i < len(filings):
                time.sleep(self.rate_limit_delay)
        
        print(f"\n{'='*60}")
        print(f"Successfully processed {len(results)} filing(s)")
        print(f"{'='*60}")
        
        return results


# # Example usage and testing
# if __name__ == "__main__":
#     from researcher_agent.src.query_parser import QueryParser, CompanyResolver
    
#     # Initialize
#     groq_client = Groq(api_key=config.QUERY_PARSER_MODEL_API_KEY)
#     parser = QueryParser(groq_client)
#     resolver = CompanyResolver()
#     fetcher = SECDataFetcher()
    
#     # Parse query
#     result = parser.parse_query(
#         "Can you analyze Amazon's financial health and growth potential over the last 3 years?"
#     )
#     print(f"\nParsed Query: {json.dumps(result, indent=2)}")
    
#     # Resolve company
#     company_info = resolver.resolve(result['company'])
#     print(f"\nResolved Company: {json.dumps(company_info, indent=2)}")
    
#     # Fetch 10-K filing
#     print(f"\nFetching 10-K filing for {company_info['ticker']}...")
#     filing_data = fetcher.fetch_filing_with_sections(
#         company_info['ticker'],
#         "10-K"
#     )
    
#     if filing_data:
#         print(f"\n{'='*60}")
#         print(f"Successfully fetched {filing_data['filing_metadata']['formType']}")
#         print(f"Company: {filing_data['filing_metadata']['companyName']}")
#         print(f"Filed: {filing_data['filing_metadata']['filedAt']}")
#         print(f"Sections extracted: {len(filing_data['sections'])}")
#         print(f"{'='*60}")

#     # Fetching 10-Q filing
#     print(f"\nFetching 10-Q filing for {company_info['ticker']}...")
#     filing_data = fetcher.fetch_filing_with_sections(
#         company_info['ticker'],
#         "10-Q"
#     )

#     if filing_data:
#         print(f"\n{'='*60}")
#         print(f"Successfully fetched {filing_data['filing_metadata']['formType']}")
#         print(f"Company: {filing_data['filing_metadata']['companyName']}")
#         print(f"Filed: {filing_data['filing_metadata']['filedAt']}")
#         print(f"Sections extracted: {len(filing_data['sections'])}")
#         print(f"{'='*60}")

# Example usage and testing
if __name__ == "__main__":
    from researcher_agent.src.query_parser import QueryParser, CompanyResolver
    
    # Initialize
    groq_client = Groq(api_key=config.QUERY_PARSER_MODEL_API_KEY)
    parser = QueryParser(groq_client)
    resolver = CompanyResolver()
    fetcher = SECDataFetcher()
    
    # Parse query
    result = parser.parse_query(
        "Can you analyze Amazon's financial health and growth potential over the last 3 years?"
    )
    print(f"\nParsed Query: {json.dumps(result, indent=2)}")
    
    # Resolve company
    company_info = resolver.resolve(result['company'])
    print(f"\nResolved Company: {json.dumps(company_info, indent=2)}")
    
    # NEW: Fetch multiple filings (10-K and 10-Q) within timeline
    print(f"\n{'='*60}")
    print(f"FETCHING MULTIPLE FILINGS BY TIMELINE")
    print(f"{'='*60}")

    filing_data_list = fetcher.fetch_filings_with_sections(
        ticker=company_info['ticker'],
        time_horizon=result['time_horizon'],  # Uses parsed time horizon
        filing_types=["10-K", "10-Q"],
        max_filings=10,
        extract_sections=True  # Set to False for faster metadata-only retrieval
    )
    
    # Display summary
    if filing_data_list:
        print(f"\n{'='*60}")
        print(f"SUMMARY")
        print(f"{'='*60}")
        for filing_data in filing_data_list:
            metadata = filing_data['filing_metadata']
            sections = filing_data['sections']
            print(f"\n{metadata['formType']} | {metadata['filedAt']}")
            print(f"  Company: {metadata['companyName']}")
            print(f"  Sections: {len(sections)}")
            print(f"  Total content: {sum(len(s) for s in sections.values()):,} characters")