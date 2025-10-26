"""
Data Acquisition Module - FINAL VERSION
Fetches data from Wikipedia and News APIs with JSON ticker support
"""

import requests
import wikipediaapi
import pandas as pd
import json
import os
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/data_acquisition.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CompanyTickerMatcher:
    """Matches company names to ticker symbols - supports JSON and CSV formats"""
    
    def __init__(self, ticker_file: str = "data/company_tickers.json"):
        self.ticker_file = ticker_file
        self.ticker_df = None
        self.ticker_data = None
        self.load_tickers()
    
    def load_tickers(self):
        """Load ticker data from JSON or CSV file"""
        try:
            if not os.path.exists(self.ticker_file):
                logger.warning(f"⚠️ Ticker file not found: {self.ticker_file}")
                self.ticker_df = pd.DataFrame(columns=['ticker', 'title', 'cik_str'])
                return
            
            file_ext = os.path.splitext(self.ticker_file)[1].lower()
            
            if file_ext == '.json':
                self._load_json()
            elif file_ext == '.csv':
                self._load_csv()
            else:
                logger.error(f"❌ Unsupported file format: {file_ext}")
                self.ticker_df = pd.DataFrame(columns=['ticker', 'title', 'cik_str'])
                
        except Exception as e:
            logger.error(f"❌ Error loading ticker file: {e}")
            self.ticker_df = pd.DataFrame(columns=['ticker', 'title', 'cik_str'])
    
    def _load_json(self):
        """Load JSON format ticker file (SEC format)"""
        with open(self.ticker_file, 'r') as f:
            self.ticker_data = json.load(f)
        
        records = []
        for key, value in self.ticker_data.items():
            records.append({
                'ticker': value.get('ticker', ''),
                'title': value.get('title', ''),
                'cik_str': value.get('cik_str', ''),
                'index': key
            })
        
        self.ticker_df = pd.DataFrame(records)
        logger.info(f"✅ Loaded {len(self.ticker_df)} tickers from JSON file")
    
    def _load_csv(self):
        """Load CSV format ticker file"""
        self.ticker_df = pd.read_csv(self.ticker_file)
        if 'name' in self.ticker_df.columns and 'title' not in self.ticker_df.columns:
            self.ticker_df['title'] = self.ticker_df['name']
        if 'symbol' in self.ticker_df.columns and 'ticker' not in self.ticker_df.columns:
            self.ticker_df['ticker'] = self.ticker_df['symbol']
        logger.info(f"✅ Loaded {len(self.ticker_df)} tickers from CSV file")
    
    def match_company(self, user_input: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Match user input to company name and ticker
        Returns: Tuple[ticker, company_name, cik]
        """
        if self.ticker_df is None or self.ticker_df.empty:
            logger.warning("No ticker data available")
            return None, user_input, None
        
        user_input_lower = user_input.lower().strip()
        
        # 1. Direct ticker match
        ticker_match = self.ticker_df[
            self.ticker_df['ticker'].str.lower() == user_input_lower
        ]
        if not ticker_match.empty:
            result = ticker_match.iloc[0]
            logger.info(f"✅ Matched ticker: {result['ticker']} -> {result['title']}")
            return result['ticker'], result['title'], str(result.get('cik_str', ''))
        
        # 2. Exact company name match
        exact_name_match = self.ticker_df[
            self.ticker_df['title'].str.lower() == user_input_lower
        ]
        if not exact_name_match.empty:
            result = exact_name_match.iloc[0]
            logger.info(f"✅ Exact name match: {result['title']} -> {result['ticker']}")
            return result['ticker'], result['title'], str(result.get('cik_str', ''))
        
        # 3. Partial name match
        partial_match = self.ticker_df[
            self.ticker_df['title'].str.lower().str.contains(user_input_lower, na=False)
        ]
        if not partial_match.empty:
            result = partial_match.iloc[0]
            logger.info(f"✅ Partial match: {result['title']} -> {result['ticker']}")
            return result['ticker'], result['title'], str(result.get('cik_str', ''))
        
        # 4. Reverse partial match
        for idx, row in self.ticker_df.iterrows():
            if row['title'].lower() in user_input_lower:
                logger.info(f"✅ Reverse match: {row['title']} -> {row['ticker']}")
                return row['ticker'], row['title'], str(row.get('cik_str', ''))
        
        # 5. Fuzzy word match
        user_words = set(user_input_lower.split())
        best_match = None
        best_score = 0
        
        for idx, row in self.ticker_df.iterrows():
            title_words = set(row['title'].lower().split())
            overlap = len(user_words.intersection(title_words))
            if overlap > best_score:
                best_score = overlap
                best_match = row
        
        if best_score >= 1:
            logger.info(f"✅ Fuzzy match: {best_match['title']} -> {best_match['ticker']} (score: {best_score})")
            return best_match['ticker'], best_match['title'], str(best_match.get('cik_str', ''))
        
        logger.warning(f"⚠️ No match found for: {user_input}")
        return None, user_input, None
    
    def search_companies(self, query: str, limit: int = 5) -> pd.DataFrame:
        """Search for companies and return top matches"""
        if self.ticker_df is None or self.ticker_df.empty:
            return pd.DataFrame()
        
        query_lower = query.lower()
        matches = self.ticker_df[
            (self.ticker_df['ticker'].str.lower().str.contains(query_lower, na=False)) |
            (self.ticker_df['title'].str.lower().str.contains(query_lower, na=False))
        ]
        return matches.head(limit)


class WikipediaDataFetcher:
    """Fetches comprehensive Wikipedia data for companies"""
    
    def __init__(self, user_agent: str = 'CompanyResearchPipeline/1.0 (research@example.com)'):
        self.wiki = wikipediaapi.Wikipedia(
            user_agent=user_agent,
            language='en',
            extract_format=wikipediaapi.ExtractFormat.WIKI
        )
    
    def fetch_company_data(self, company_name: str) -> Dict:
        """Fetch comprehensive Wikipedia data"""
        try:
            logger.info(f"🔍 Fetching Wikipedia data for: {company_name}")
            
            page = self.wiki.page(company_name)
            
            if not page.exists():
                logger.warning(f"⚠️ Wikipedia page not found for: {company_name}")
                search_results = self._search_wikipedia(company_name)
                if search_results:
                    page = self.wiki.page(search_results[0])
                else:
                    return {"error": f"No Wikipedia page found for {company_name}"}
            
            data = {
                "title": page.title,
                "summary": page.summary,
                "full_text": page.text,
                "url": page.fullurl,
                "sections": self._extract_sections(page),
                "categories": list(page.categories.keys()),
                "links": list(page.links.keys())[:50],
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"✅ Successfully fetched Wikipedia data for: {page.title}")
            return data
            
        except Exception as e:
            logger.error(f"❌ Error fetching Wikipedia data for {company_name}: {e}")
            return {"error": str(e)}
    
    def _search_wikipedia(self, query: str) -> List[str]:
        """Search Wikipedia for matching pages"""
        try:
            url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 5
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            results = [item['title'] for item in data.get('query', {}).get('search', [])]
            logger.info(f"🔍 Wikipedia search results for '{query}': {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Wikipedia search failed: {e}")
            return []
    
    def _extract_sections(self, page) -> List[Dict]:
        """Extract all sections from Wikipedia page"""
        sections = []
        
        def traverse_sections(section_list, level=0):
            for section in section_list:
                sections.append({
                    "title": section.title,
                    "level": level,
                    "text": section.text[:500]
                })
                if section.sections:
                    traverse_sections(section.sections, level + 1)
        
        traverse_sections(page.sections)
        return sections


class NewsAPIFetcher:
    """Fetches news articles from NewsAPI and GDELT"""
    
    def __init__(self, news_api_key: str):
        self.news_api_key = news_api_key
    
    def fetch_news(self, company_name: str, max_articles: int = 20) -> List[Dict]:
        """Fetch news articles from multiple sources"""
        articles = []
        
        newsapi_articles = self._fetch_newsapi(company_name, max_articles)
        articles.extend(newsapi_articles)
        
        if len(articles) < 5:
            gdelt_articles = self._fetch_gdelt(company_name, max_articles)
            articles.extend(gdelt_articles)
        
        unique_articles = {article['url']: article for article in articles}
        return list(unique_articles.values())[:max_articles]
    
    def _fetch_newsapi(self, company_name: str, max_articles: int) -> List[Dict]:
        """Fetch from NewsAPI.org"""
        if not self.news_api_key:
            logger.warning("⚠️ No NewsAPI key provided")
            return []
        
        try:
            logger.info(f"🔍 Fetching news from NewsAPI for: {company_name}")
            
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": company_name,
                "language": "en",
                "pageSize": max_articles,
                "sortBy": "publishedAt",
                "apiKey": self.news_api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"❌ NewsAPI returned status {response.status_code}")
                return []
            
            data = response.json()
            articles = data.get("articles", [])
            
            formatted_articles = [
                {
                    "title": article.get("title", "N/A"),
                    "url": article.get("url", "N/A"),
                    "source": article.get("source", {}).get("name", "N/A"),
                    "published_date": article.get("publishedAt", "N/A"),
                    "description": article.get("description", ""),
                    "content": article.get("content", "")
                }
                for article in articles
            ]
            
            logger.info(f"✅ Fetched {len(formatted_articles)} articles from NewsAPI")
            return formatted_articles
            
        except Exception as e:
            logger.error(f"❌ NewsAPI fetch failed: {e}")
            return []
    
    def _fetch_gdelt(self, company_name: str, max_articles: int) -> List[Dict]:
        """Fetch from GDELT Project"""
        try:
            logger.info(f"🔍 Fetching news from GDELT for: {company_name}")
            
            company_clean = company_name.replace(" ", "+")
            url = (
                f"https://api.gdeltproject.org/api/v2/doc/doc?"
                f"query={company_clean}+sourceCountry:US+sourceLang:ENGLISH"
                f"&mode=artlist&maxrecords={max_articles}&format=json"
            )
            
            response = requests.get(url, timeout=10)
            
            if not response.text.strip() or not response.text.startswith("{"):
                logger.warning("⚠️ Invalid GDELT response")
                return []
            
            data = response.json()
            articles = data.get("articles", [])
            
            english_articles = [
                {
                    "title": article.get("title", "N/A"),
                    "url": article.get("url", "N/A"),
                    "source": article.get("source", "N/A"),
                    "published_date": article.get("seendate", "N/A"),
                    "description": "",
                    "content": ""
                }
                for article in articles
                if article.get("language", "ENGLISH").lower() == "english"
            ]
            
            logger.info(f"✅ Fetched {len(english_articles)} articles from GDELT")
            return english_articles
            
        except Exception as e:
            logger.error(f"❌ GDELT fetch failed: {e}")
            return []


class DataAcquisitionPipeline:
    """Main data acquisition pipeline"""
    
    def __init__(self, news_api_key: str, ticker_file: str = "data/company_tickers.json"):
        self.ticker_matcher = CompanyTickerMatcher(ticker_file)
        self.wiki_fetcher = WikipediaDataFetcher()
        self.news_fetcher = NewsAPIFetcher(news_api_key)
    
    def fetch_company_data(self, user_input: str) -> Dict:
        """Complete data acquisition for a company"""
        logger.info(f"🚀 Starting data acquisition for: {user_input}")
        
        # Match ticker and company name
        ticker, company_name, cik = self.ticker_matcher.match_company(user_input)
        
        # Fetch Wikipedia data
        wiki_data = self.wiki_fetcher.fetch_company_data(company_name)
        
        # Fetch news articles
        news_articles = self.news_fetcher.fetch_news(company_name)
        
        # Compile results
        result = {
            "query": user_input,
            "ticker": ticker,
            "company_name": company_name,
            "cik": cik,
            "wikipedia": wiki_data,
            "news_articles": news_articles,
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "wiki_success": "error" not in wiki_data,
                "news_count": len(news_articles),
                "data_sources": ["Wikipedia", "NewsAPI", "GDELT"]
            }
        }
        
        # Save to file
        self._save_results(result)
        
        logger.info(f"✅ Data acquisition complete for: {company_name}")
        return result
    
    def _save_results(self, result: Dict):
        """Save results to JSON file"""
        os.makedirs("data/raw", exist_ok=True)
        filename = f"data/raw/{result['company_name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        
        logger.info(f"💾 Results saved to: {filename}")


def main():
    """Example usage"""
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "d95b2db0967748a69be7b951bed9e4bc")
    pipeline = DataAcquisitionPipeline(NEWS_API_KEY)
    
    user_input = input("Enter company name or ticker: ")
    result = pipeline.fetch_company_data(user_input)
    
    print(f"\n{'='*50}")
    print(f"Company: {result['company_name']}")
    print(f"Ticker: {result['ticker']}")
    print(f"CIK: {result['cik']}")
    print(f"Wikipedia Found: {result['metadata']['wiki_success']}")
    print(f"News Articles: {result['metadata']['news_count']}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()