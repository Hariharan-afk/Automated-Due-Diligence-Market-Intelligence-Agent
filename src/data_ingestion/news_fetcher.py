# src/data_ingestion/news_fetcher.py
"""Fetcher for news articles - Smart relevance scoring for any company"""

import requests
import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data_ingestion.base_fetcher import BaseFetcher
from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class NewsFetcher(BaseFetcher):
    """
    Fetches news articles using NewsAPI and GDELT
    
    Features:
    - Smart relevance scoring (works for ANY company)
    - Word-boundary matching (prevents false positives)
    - English-only filtering
    - Dual-source (NewsAPI + GDELT)
    """
    
    def __init__(self, mode: str = "auto"):
        """
        Initialize news fetcher
        
        Args:
            mode: "newsapi", "gdelt", or "auto" (tries both)
        """
        super().__init__(rate_limit=5.0, max_retries=3)
        
        self.mode = mode
        self.news_api_key = getattr(config.api, 'news_api_key', '')
        
        self.newsapi_base_url = "https://newsapi.org/v2/everything"
        self.gdelt_base_url = "https://api.gdeltproject.org/api/v2/doc/doc"
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DataPipeline/1.0 (Educational Project)"
        })
        
        logger.info(f"NewsFetcher initialized (mode: {mode}, smart scoring)")
    
    def fetch_by_ticker(
        self,
        ticker: str,
        days_back: int = 3,
        max_records: int = 100,
        relevance_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Fetch news with smart relevance filtering
        
        Args:
            ticker: Company ticker
            days_back: Days back (default 3)
            max_records: Max articles
            relevance_threshold: Minimum relevance score (0.0-1.0, default 0.3)
            
        Returns:
            List of relevant English articles with scores
        """
        company = config.get_company_by_ticker(ticker)
        if not company:
            raise ValueError(f"Company {ticker} not found in config")
        
        company_name = company['name']
        articles = []
        
        # Try NewsAPI first
        if self.mode in ["newsapi", "auto"] and self.news_api_key:
            logger.info(f"Trying NewsAPI for {ticker}...")
            try:
                articles = self._fetch_from_newsapi(ticker, company_name, days_back, max_records)
                logger.info(f"NewsAPI: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"NewsAPI failed: {e}")
        
        # Try GDELT if NewsAPI didn't work
        if (not articles and self.mode in ["gdelt", "auto"]) or self.mode == "gdelt":
            logger.info(f"Trying GDELT for {ticker}...")
            try:
                articles = self._fetch_from_gdelt(ticker, company_name, days_back, max_records)
                logger.info(f"GDELT: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"GDELT failed: {e}")
        
        if not articles:
            logger.warning(f"No articles found for {ticker}")
            return []
        
        # Filter with smart scoring
        print(f"\n   🔍 SCORING {len(articles)} articles...")
        filtered = self._filter_by_relevance(articles, ticker, company_name, relevance_threshold)
        print(f"   ✅ Kept {len(filtered)} articles (score >= {relevance_threshold})\n")
        
        # Add metadata
        for article in filtered:
            article['ticker'] = ticker
            article['company_name'] = company_name
        
        # Deduplicate
        filtered = self.deduplicate_articles(filtered)
        
        logger.info(f"Final: {len(filtered)} articles for {ticker}")
        
        return filtered
    
    def _fetch_from_newsapi(self, ticker, company_name, days_back, max_records):
        """Fetch from NewsAPI"""
        clean_name = self._clean_company_name(company_name)
        query = f'"{ticker}" OR "{clean_name}"'
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        params = {
            "q": query,
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
            "language": "en",
            "sortBy": "relevancy",
            "pageSize": min(max_records, 100),
            "apiKey": self.news_api_key
        }
        
        response = self.session.get(self.newsapi_base_url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status') != 'ok':
            raise Exception(f"NewsAPI error: {data.get('message')}")
        
        return self._parse_newsapi_response(data)
    
    def _fetch_from_gdelt(self, ticker, company_name, days_back, max_records):
        """Fetch from GDELT"""
        clean_name = self._clean_company_name(company_name)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        params = {
            "query": clean_name,
            "mode": "artlist",
            "maxrecords": max_records,
            "format": "json",
            "startdatetime": start_date.strftime("%Y%m%d000000"),
            "enddatetime": end_date.strftime("%Y%m%d235959"),
            "sourcelang": "eng"
        }
        
        response = self.session.get(self.gdelt_base_url, params=params, timeout=15)
        response.raise_for_status()
        
        if not response.text or len(response.text) < 10:
            return []
        
        try:
            data = response.json()
            articles = self._parse_gdelt_response(data)
            
            # Filter English only
            english_only = [a for a in articles if self._is_english(a.get('title', ''))]
            
            return english_only
        except:
            return []
    
    def _parse_newsapi_response(self, data: Dict) -> List[Dict[str, Any]]:
        """Parse NewsAPI response"""
        articles = []
        
        for item in data.get('articles', []):
            published_at = item.get('publishedAt', '')
            try:
                pub_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
            except:
                pub_date = datetime.now()
            
            articles.append({
                "url": item.get('url') or '',
                "title": item.get('title') or 'No Title',
                "description": item.get('description') or '',
                "source": (item.get('source') or {}).get('name', 'Unknown'),
                "author": item.get('author') or '',
                "published_date": pub_date,
                "content": item.get('content') or '',
                "language": "en",
                "api_source": "newsapi"
            })
        
        return articles
    
    def _parse_gdelt_response(self, data: Dict) -> List[Dict[str, Any]]:
        """Parse GDELT response"""
        articles = []
        
        for item in data.get('articles', []):
            date_str = item.get('seendate', '')
            try:
                pub_date = datetime.strptime(date_str, "%Y%m%d%H%M%S")
            except:
                pub_date = datetime.now()
            
            articles.append({
                "url": item.get('url') or '',
                "title": item.get('title') or 'No Title',
                "description": '',
                "source": item.get('domain', 'Unknown'),
                "author": '',
                "published_date": pub_date,
                "content": '',
                "language": item.get('language', 'en'),
                "api_source": "gdelt"
            })
        
        return articles
    
    @staticmethod
    def _is_english(text: str) -> bool:
        """Check if text is English (no Chinese, Japanese, etc.)"""
        if not text:
            return False
        
        # Check for non-Latin scripts
        non_latin_pattern = r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\u0600-\u06ff\u0400-\u04ff]'
        
        if re.search(non_latin_pattern, text):
            return False
        
        # Check Latin character ratio
        latin_chars = sum(1 for c in text if c.isalpha() and ord(c) < 128)
        total_chars = sum(1 for c in text if c.isalpha())
        
        if total_chars == 0:
            return True
        
        return (latin_chars / total_chars) >= 0.8
    
    @staticmethod
    def _has_word_boundary_match(text: str, term: str) -> bool:
        """
        Word-boundary matching - prevents false positives
        
        Examples:
        - "BAC stock rises" → TRUE (BAC is standalone word)
        - "Chelsea's backup system" → FALSE (bac is part of backup)
        - "$MSFT earnings" → TRUE (MSFT with symbol prefix)
        """
        if not text or not term:
            return False
        
        # Match term as complete word, not substring
        pattern = r'\b' + re.escape(term) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))
    
    def _calculate_relevance_score(
        self,
        article: Dict,
        ticker: str,
        company_name: str
    ) -> float:
        """
        Calculate relevance score (0.0 to 1.0)
        
        Works for ANY company - uses generic signals:
        - Ticker presence (word boundaries)
        - Company name presence
        - Business context keywords
        - Content depth
        
        No company-specific hardcoded keywords!
        """
        score = 0.0
        
        title = article.get("title", "")
        desc = article.get("description", "")
        content = article.get("content", "")
        
        title_lower = title.lower()
        desc_lower = desc.lower()
        company_lower = self._clean_company_name(company_name).lower()
        
        # Get first word of company (e.g., "Apple" from "Apple Inc.")
        base_company = company_lower.split()[0] if company_lower else ""
        
        # 1. Ticker in title (STRICT word boundary)
        if self._has_word_boundary_match(title, ticker):
            score += 0.5
        
        # 2. Company name in title
        if company_lower in title_lower or base_company in title_lower:
            score += 0.4
        
        # 3. Title starts with company (very relevant)
        if title_lower.startswith(company_lower) or title_lower.startswith(base_company):
            score += 0.3
        
        # 4. Ticker in description/content (word boundary)
        full_text = f"{desc} {content}"
        if self._has_word_boundary_match(full_text, ticker):
            score += 0.2
        
        # 5. Business context (generic - works for all companies)
        business_keywords = [
            'stock', 'share', 'shares', 'earnings', 'revenue',
            'market', 'nasdaq', 'nyse', 'ceo', 'quarter', 'profit',
            'analyst', 'investor', 'trading', 'financial', 'valuation'
        ]
        
        if any(kw in title_lower or kw in desc_lower for kw in business_keywords):
            score += 0.2
        
        # 6. Multiple mentions
        company_count = title_lower.count(company_lower) + desc_lower.count(company_lower)
        company_count += title_lower.count(base_company) + desc_lower.count(base_company)
        
        # Count ticker with word boundaries
        ticker_pattern = r'\b' + re.escape(ticker) + r'\b'
        ticker_count = len(re.findall(ticker_pattern, f"{title} {desc}", re.IGNORECASE))
        
        total_mentions = company_count + ticker_count
        
        if total_mentions >= 3:
            score += 0.2
        elif total_mentions >= 2:
            score += 0.1
        
        return min(score, 1.0)
    
    def _filter_by_relevance(
        self,
        articles: List[Dict[str, Any]],
        ticker: str,
        company_name: str,
        threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Filter using relevance scores
        
        Args:
            articles: List of articles
            ticker: Company ticker
            company_name: Company name
            threshold: Minimum score to keep (0.3 = moderate relevance)
            
        Returns:
            Filtered and sorted articles
        """
        filtered = []
        
        for article in articles:
            # Language check first
            if not self._is_english(article.get('title', '')):
                continue
            
            # Calculate relevance score
            score = self._calculate_relevance_score(article, ticker, company_name)
            
            if score >= threshold:
                article['relevance_score'] = round(score, 2)
                filtered.append(article)
                
                # Debug output
                print(f"   ✅ {article.get('title', '')[:50]}")
                print(f"      Score: {article['relevance_score']}")
            else:
                print(f"   ❌ {article.get('title', '')[:50]}")
                print(f"      Score: {round(score, 2)} (below {threshold})")
        
        # Sort by relevance score (highest first)
        filtered.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return filtered
    
    @staticmethod
    def _clean_company_name(company_name: str) -> str:
        """Remove corporate suffixes"""
        name = company_name
        
        suffixes = [
            " Inc.", " Inc", " Corporation", " Corp.", " Corp",
            " LLC", " L.L.C.", " Ltd.", " Ltd", " Company", " Co.",
            " plc", " PLC", ".com", " Platforms", " Group"
        ]
        
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        
        return name.strip()
    
    def deduplicate_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicates"""
        seen_urls = set()
        seen_titles = set()
        deduplicated = []
        
        for article in articles:
            url = article.get('url', '')
            title = (article.get('title') or '').lower().strip()
            
            if url in seen_urls or title in seen_titles:
                continue
            
            seen_urls.add(url)
            seen_titles.add(title)
            deduplicated.append(article)
        
        removed = len(articles) - len(deduplicated)
        if removed > 0:
            logger.info(f"Removed {removed} duplicates")
        
        return deduplicated
    
    def fetch(self, query: str, days_back: int = 3, max_records: int = 100, language: str = "en"):
        """Generic fetch method"""
        if self.mode == "newsapi" and self.news_api_key:
            return self._fetch_newsapi_generic(query, days_back, max_records, language)
        elif self.mode in ["gdelt", "auto"]:
            return self._fetch_gdelt_generic(query, days_back, max_records)
        return []
    
    def _fetch_newsapi_generic(self, query, days_back, max_records, language):
        """Generic NewsAPI fetch"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        params = {
            "q": query,
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
            "language": language,
            "sortBy": "relevancy",
            "pageSize": min(max_records, 100),
            "apiKey": self.news_api_key
        }
        
        try:
            response = self.session.get(self.newsapi_base_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'ok':
                return self._parse_newsapi_response(data)
        except Exception as e:
            logger.error(f"NewsAPI failed: {e}")
        
        return []
    
    def _fetch_gdelt_generic(self, query, days_back, max_records):
        """Generic GDELT fetch"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        params = {
            "query": query,
            "mode": "artlist",
            "maxrecords": max_records,
            "format": "json",
            "startdatetime": start_date.strftime("%Y%m%d000000"),
            "enddatetime": end_date.strftime("%Y%m%d235959"),
            "sourcelang": "eng"
        }
        
        try:
            response = self.session.get(self.gdelt_base_url, params=params, timeout=15)
            response.raise_for_status()
            
            if response.text and len(response.text) > 10:
                data = response.json()
                articles = self._parse_gdelt_response(data)
                return [a for a in articles if self._is_english(a.get('title', ''))]
        except:
            pass
        
        return []