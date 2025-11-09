# researcher_agent/src/query_parser.py
import re
from typing import Dict, List, Any
import json
from groq import Groq
import utils.config


class QueryParser:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def parse_query(self, user_query: str) -> Dict[str, Any]:
        """
        Parse user query to extract structured information with error handling
        """
        try:
            prompt = f"""
            Analyze this user query and extract structured information.
            If information is not clear from the query, make reasonable assumptions.
            
            User Query: "{user_query}"
            
            Return JSON format:
            {{
                "company": "company name",
                "ticker": "company ticker", 
                "analysis_type": "investment_analysis|risk_assessment|financial_health|general",
                "focus_areas": ["area1", "area2"],
                "depth": "quick_summary|standard|comprehensive",
                "time_horizon": "current_year|last_3_years|last_5_years|custom"
            }}
            """
            
            response = self.llm.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=500
            )
            
            parsed = json.loads(response.choices[0].message.content)
            
            # Validate required fields
            return {
                "company": parsed.get("company", ""),
                "ticker": parsed.get("ticker", ""),
                "analysis_type": parsed.get("analysis_type", "general"),
                "focus_areas": parsed.get("focus_areas", []),
                "depth": parsed.get("depth", "standard"),
                "time_horizon": parsed.get("time_horizon", "current_year")
            }
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return self._get_default_structure()
        except Exception as e:
            print(f"Error in parse_query: {e}")
            return self._get_default_structure()
    
    def _get_default_structure(self) -> Dict[str, Any]:
        """Return default structure when parsing fails"""
        return {
            "company": "",
            "ticker": "",
            "analysis_type": "general",
            "focus_areas": [],
            "depth": "standard",
            "time_horizon": "current_year"
        }

# # Example usage:
# parser = QueryParser(openai_client)
# result = parser.parse_query("Deep analysis on Apple Inc for investment opportunities")

# Output:
# {
#     "company": "Apple Inc",
#     "analysis_type": "investment_analysis",
#     "focus_areas": ["financial_performance", "growth_potential", "risks", "market_position"],
#     "depth": "comprehensive",
#     "time_horizon": "current_year"
# }


class CompanyResolver:
    def __init__(self):
        self.company_map = self._load_company_map()
    
    def _load_company_map(self) -> Dict:
        """
        Load and transform SEC company tickers mapping into searchable format
        """
        with open('researcher_agent/assets/company_tickers.json', 'r') as file:
            raw_data = json.load(file)
        
        # Transform to searchable format
        company_map = {}
        for entry in raw_data.values():
            ticker = entry['ticker'].upper()
            title = entry['title'].upper()
            cik = str(entry['cik_str']).zfill(10)  # CIK with leading zeros
            
            # Add multiple lookup keys
            company_map[ticker] = {'ticker': ticker, 'title': entry['title'], 'cik': cik}
            company_map[title] = {'ticker': ticker, 'title': entry['title'], 'cik': cik}
        
        return company_map
    
    def resolve(self, company_identifier: str) -> Dict:
        """
        Resolve company name/ticker to standard format
        """
        key = company_identifier.upper().strip()
        
        # Direct lookup
        if key in self.company_map:
            return self.company_map[key]
        
        # Fuzzy matching for partial names
        for name, info in self.company_map.items():
            if key in name or name in key:
                return info
        
        raise ValueError(f"Company not found: {company_identifier}")

# # Example usage:
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


