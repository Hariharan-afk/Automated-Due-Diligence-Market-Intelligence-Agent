# # researcher_agent/src/data_fetcher.py
# import json
# from sec_api import QueryApi
# import os
# from researcher_agent.src.query_parser import QueryParser, CompanyResolver
# from groq import Groq
# import utils.config


# def fetch_sec_filings(ticker: str, start_date: str, end_date: str):
#     queryApi = QueryApi(api_key=utils.config.SEC_API_KEY)
#     search_query = f'ticker:{ticker} AND formType:"10-K" AND filedAt:[{start_date} TO {end_date}]'

#     parameters = {
#         "query": search_query,
#         "from": "0",
#         "size": "50",
#         "sort": [{"filedAt": {"order": "desc"}}],
#     }

#     response = queryApi.get_filings(parameters)
#     return response

# # import json

# # print("Apple's 10-K filing metdata:")
# # print(json.dumps(response["filings"][0], indent=2))


# groq_client = Groq(api_key = utils.config.QUERY_PARSER_MODEL_API_KEY)
# parser = QueryParser(groq_client)

# # Parse a query
# result = parser.parse_query(
#     "Can you analyze Amazon's financial health and growth potential over the last 3 years?"
# )
# print(result)

# resolver = CompanyResolver()

# # Company_Ticker = resolver.resolve(result['company'])
# company_info = resolver.resolve(result['company'])
# print(company_info)
# # Output: {'cik': '0000320193', 'name': 'Apple Inc.', 'ticker': 'AAPL'}

# # Example usage
# response = fetch_sec_filings(company_info['ticker'], "2021-01-01", "2024-12-31")
# print(f"Number of 10-K filings from {company_info['title']} between 2021 and 2024:\n {response['total']['value']}")




# researcher_agent/src/data_fetcher.py
import json
import time
from typing import Dict, List, Optional
from sec_api import QueryApi, ExtractorApi
from groq import Groq

from utils.config import config


class SECDataFetcher:
    """Handles fetching and extracting data from SEC filings"""
    
    def __init__(self):
        self.query_api = QueryApi(api_key=config.SEC_API_KEY)
        self.extractor_api = ExtractorApi(api_key=config.SEC_API_KEY)
        self.rate_limit_delay = 1.0 / config.SEC_API_RATE_LIMIT  # seconds between requests
    
    def fetch_latest_filing(
        self, 
        ticker: str, 
        filing_type: str = "10-K"
    ) -> Optional[Dict]:
        """
        Fetch metadata for the most recent filing of a specific type
        
        Args:
            ticker: Company ticker symbol
            filing_type: Type of filing (10-K, 10-Q, etc.)
            
        Returns:
            Filing metadata dictionary or None if not found
        """
        try:
            query = {
                "query": f'ticker:{ticker} AND formType:"{filing_type}"',
                "from": "0",
                "size": "1",
                "sort": [{"filedAt": {"order": "desc"}}]
            }
            
            response = self.query_api.get_filings(query)
            
            if not response.get('filings'):
                print(f"No {filing_type} filings found for {ticker}")
                return None
            
            filing = response['filings'][0]
            print(f"✓ Found {filing_type} for {ticker}: Filed {filing['filedAt']}")
            
            return filing
            
        except Exception as e:
            print(f"✗ Error fetching filing metadata: {e}")
            return None
    
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
    
    def fetch_filing_with_sections(
        self, 
        ticker: str, 
        filing_type: str = "10-K"
    ) -> Optional[Dict]:
        """
        Complete workflow: Fetch filing metadata and extract all sections
        
        Args:
            ticker: Company ticker symbol
            filing_type: Type of filing
            
        Returns:
            Dictionary containing filing metadata and extracted sections
        """
        # Step 1: Get filing metadata
        filing_metadata = self.fetch_latest_filing(ticker, filing_type)
        
        if not filing_metadata:
            return None
        
        # Step 2: Extract sections
        print(f"\nExtracting sections from {filing_type}...")
        sections = self.extract_sections(
            filing_metadata['linkToFilingDetails'],
            filing_type
        )
        
        if not sections:
            print(f"✗ No sections could be extracted from {filing_type}")
            return None
        
        return {
            'filing_metadata': filing_metadata,
            'sections': sections
        }


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