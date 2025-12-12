import os
import json
import requests
import newspaper
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import Levenshtein
from fuzzywuzzy import fuzz

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
        
        # Business keywords for context scoring
        self.business_keywords = [
            'stock', 'share', 'shares', 'earnings', 'revenue', 'profit', 'loss',
            'market', 'nasdaq', 'nyse', 'ceo', 'cfo', 'quarter', 'results', 'trade',
            'analyst', 'investor', 'trading', 'financial', 'valuation', 'dividend',
            'forecast', 'guidance', 'merger', 'acquisition', 'layoff', 'hire', 'ipo', 
            'partnership', 'bankruptcy', 'expansion', 'contract', 'sale', 'deal', 
            'acquire', 'regulation', 'lawsuit', 'litigation', 'strike' 
        ]
        
        logger.info(f"NewsFetcher initialized (mode={self.mode})")

    def _extract_name_variations(self, company_name: str) -> List[str]:
        """Generate common name variations for fuzzy matching"""
        clean_name = self._clean_company_name(company_name)
        words = clean_name.split()
        
        variations = set()
        
        # Full clean name
        variations.add(clean_name)
        
        # First word only (e.g., "Apple" from "Apple Inc")
        if words:
            variations.add(words[0])
        
        # Common abbreviations
        if len(words) > 1:
            # First letter of each word
            acronym = ''.join(word[0] for word in words if word)
            if len(acronym) >= 2:
                variations.add(acronym)
        
        # Without "The" prefix
        if words and words[0].lower() == 'the':
            variations.add(' '.join(words[1:]))
        
        return list(variations)

    def _calculate_fuzzy_scores(self, text: str, company_name: str, ticker: str) -> Dict[str, float]:
        """Calculate multiple fuzzy matching scores"""
        text_lower = text.lower()
        company_lower = company_name.lower()
        variations = self._extract_name_variations(company_name)
        
        scores = {}
        
        # 1. Exact matches
        scores['exact_company'] = 1.0 if company_lower in text_lower else 0.0
        scores['exact_ticker'] = 1.0 if self._has_word_boundary_match(text, ticker) else 0.0
        
        # 2. Fuzzy matches for company name variations
        fuzzy_scores = []
        for variation in variations:
            if len(variation) < 2:  # Skip very short variations
                continue
                
            # Partial ratio (substring match)
            partial_score = fuzz.partial_ratio(variation, text_lower) / 100.0
            # Token set ratio (handles word order changes)
            token_score = fuzz.token_set_ratio(variation, text_lower) / 100.0
            # Weighted average
            fuzzy_scores.append(max(partial_score, token_score * 0.8))
        
        scores['fuzzy_company'] = max(fuzzy_scores) if fuzzy_scores else 0.0
        
        # 3. Position-based scoring
        if text_lower.startswith(company_lower):
            scores['position'] = 1.0
        elif company_lower in text_lower[:100]:  # First 100 chars
            scores['position'] = 0.7
        else:
            scores['position'] = 0.3
        
        return scores

    def _analyze_semantic_context(self, text: str) -> Dict[str, float]:
        """Analyze semantic context using business keywords"""
        text_lower = text.lower()
        
        # Count business keywords
        business_matches = sum(1 for kw in self.business_keywords if kw in text_lower)
        
        # Calculate business context score
        word_count = len(text_lower.split())
        business_score = min(business_matches / max(word_count / 50, 1), 1.0)
        
        return {
            'business_context': business_score,
            'has_org_entities': 0.5,  
        }

    def _calculate_mention_density(self, text: str, company_name: str, ticker: str) -> float:
        """Calculate how densely the company is mentioned"""
        text_lower = text.lower()
        company_lower = company_name.lower()
        variations = self._extract_name_variations(company_name)
        
        total_mentions = 0
        
        # Count company name mentions
        total_mentions += text_lower.count(company_lower)
        
        # Count variation mentions
        for variation in variations:
            if len(variation) >= 2:
                total_mentions += text_lower.count(variation.lower())
        
        # Count ticker mentions with word boundaries
        ticker_pattern = r'\b' + re.escape(ticker) + r'\b'
        ticker_mentions = len(re.findall(ticker_pattern, text, re.IGNORECASE))
        total_mentions += ticker_mentions
        
        # Normalize by text length
        word_count = len(text_lower.split())
        density = total_mentions / max(word_count / 100, 1)  # Mentions per 100 words
        
        return min(density, 1.0)

    def _calculate_relevance_score(
        self,
        article: Dict,
        ticker: str,
        company_name: str
    ) -> float:
        """
        Enhanced relevance scoring with multiple signals
        
        Works for ANY company - uses robust fuzzy matching:
        - Multiple name variations
        - Fuzzy matching algorithms  
        - Business context analysis
        - Mention density
        """
        title = article.get("title", "")
        description = article.get("description", "")
        content = article.get("content", "")
        
        # Combine text fields with weights
        full_text = f"{title} {description} {content}"
        weighted_text = f"{title} {title} {description} {content}"  # Title has double weight
        
        # Calculate component scores
        fuzzy_scores = self._calculate_fuzzy_scores(weighted_text, company_name, ticker)
        semantic_scores = self._analyze_semantic_context(full_text)
        mention_density = self._calculate_mention_density(full_text, company_name, ticker)
        
        # Weighted scoring
        weights = {
            # Fuzzy matching (40%)
            'exact_company': 0.15,
            'exact_ticker': 0.15,
            'fuzzy_company': 0.10,
            
            # Semantic context (30%)
            'business_context': 0.20,
            'has_org_entities': 0.10,
            
            # Structural signals (30%)
            'position': 0.10,
            'mention_density': 0.20
        }
        
        # Combine scores
        total_score = 0.0
        
        # Add fuzzy scores
        total_score += fuzzy_scores['exact_company'] * weights['exact_company']
        total_score += fuzzy_scores['exact_ticker'] * weights['exact_ticker']
        total_score += fuzzy_scores['fuzzy_company'] * weights['fuzzy_company']
        
        # Add semantic scores
        total_score += semantic_scores['business_context'] * weights['business_context']
        total_score += semantic_scores['has_org_entities'] * weights['has_org_entities']
        
        # Add structural scores
        total_score += fuzzy_scores['position'] * weights['position']
        total_score += mention_density * weights['mention_density']
        
        # Boost for title matches
        title_fuzzy = self._calculate_fuzzy_scores(title, company_name, ticker)
        if title_fuzzy['exact_company'] > 0 or title_fuzzy['exact_ticker'] > 0:
            total_score = min(total_score + 0.1, 1.0)
        
        return round(total_score, 3)

    # ALL OTHER METHODS REMAIN EXACTLY THE SAME AS YOUR ORIGINAL CODE
    def fetch_by_ticker(
        self,
        ticker: str,
        days_back: int = 30,
        max_records: int = 80,
        relevance_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Fetch news for a ticker with full content extraction
        
        Args:
            ticker: Company ticker
            days_back: Number of days to look back (default: 7)
            max_records: Max records to return (default: 20)
            relevance_threshold: Minimum relevance score (default: 0.6)
        
        Returns:
            List of news articles with full content
        """
        company = config.get_company_by_ticker(ticker)
        company_name = company.name if company else ticker
        
        logger.info(f"Fetching news for {ticker} ({company_name}) - last {days_back} days")
        
        articles = []
        
        # 1. Fetch from NewsAPI
        if self.mode in ["newsapi", "auto"] and self.news_api_key:
            try:
                newsapi_articles = self._fetch_from_newsapi(ticker, company_name, days_back, max_records * 2)
                articles.extend(newsapi_articles)
            except Exception as e:
                logger.error(f"NewsAPI fetch failed: {e}")
        
        # 2. Fetch from GDELT (if needed)
        if self.mode in ["gdelt", "auto"] and len(articles) < max_records:
            try:
                gdelt_articles = self._fetch_from_gdelt(ticker, company_name, days_back, max_records * 2)
                articles.extend(gdelt_articles)
            except Exception as e:
                logger.error(f"GDELT fetch failed: {e}")
        
        if not articles:
            logger.warning(f"No articles found for {ticker}")
            return []
        
        # 3. Deduplicate
        unique_articles = self.deduplicate_articles(articles)
        
        # 4. Calculate relevance scores and filter
        relevant_articles = []
        for article in unique_articles:
            score = self._calculate_relevance_score(article, ticker, company_name)
            article['relevance_score'] = score
            
            if score >= relevance_threshold:
                relevant_articles.append(article)
        
        # Sort by relevance (highest first)
        relevant_articles.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        # Limit to max_records
        final_articles = relevant_articles[:max_records]
        
        logger.info(f"After filtering: {len(final_articles)} relevant articles")
        
        # 5. Extract full content using newspaper3k
        logger.info(f"Extracting full content for {len(final_articles)} articles...")
        articles_with_content = []
        
        for i, article in enumerate(final_articles):
            url = article.get('url')
            if not url:
                logger.debug(f"[{i+1}/{len(final_articles)}] No URL, skipping")
                continue
            
            # Check if content is truncated NewsAPI format
            original_content = article.get('content', '')
            is_truncated = '[+' in original_content and 'chars]' in original_content
            
            logger.debug(f"[{i+1}/{len(final_articles)}] URL: {url[:60]}...")
            logger.debug(f"  Original content length: {len(original_content)} chars, truncated: {is_truncated}")
            
            try:
                # Use newspaper3k to extract full article content
                news_article = newspaper.Article(url)
                news_article.download()
                news_article.parse()
                
                # Get the full text content
                full_text = news_article.text

                logger.debug(f"  Newspaper3k extracted: {len(full_text)} chars")
                
                # Only keep articles with substantial content
                if full_text and len(full_text) > 200:  # At least 200 chars
                    article['content'] = full_text
                    article['newsapi_truncated_content'] = original_content
                    article['content_length'] = len(full_text)
                    article['extraction_method'] = 'newspaper3k'
                    article['authors'] = news_article.authors
                    article['publish_date'] = news_article.publish_date
                    articles_with_content.append(article)
                    logger.debug(f"✓ [{i+1}/{len(final_articles)}] Extracted: {article.get('title', '')[:50]}... ({len(full_text)} chars)")
                else:
                    logger.debug(f"✗ [{i+1}/{len(final_articles)}] Insufficient content from: {article.get('title', '')[:50]}...")
                    
            except Exception as e:
                logger.warning(f"✗ [{i+1}/{len(final_articles)}] Extraction failed: {str(e)[:100]}")
                # Fallback: use NewsAPI content even if truncated
                if len(original_content) > 50:
                    article['extraction_method'] = 'newsapi_truncated'
                    articles_with_content.append(article)
                    logger.info(f"⚠ [{i+1}/{len(final_articles)}] Using NewsAPI content ({len(original_content)} chars)")
                continue

        logger.info(f"Successfully extracted {len(articles_with_content)} articles")
        logger.info(f"  Full extractions: {sum(1 for a in articles_with_content if a.get('extraction_method') == 'newspaper3k')}")
        logger.info(f"  NewsAPI fallbacks: {sum(1 for a in articles_with_content if a.get('extraction_method') == 'newsapi_truncated')}")

        return articles_with_content

    def _fetch_from_newsapi(self, ticker: str, company_name: str, days_back: int, max_records: int) -> List[Dict[str, Any]]:
        """Fetch from NewsAPI"""
        if not self.news_api_key:
            logger.warning("NewsAPI key not found, skipping")
            return []
            
        query = f"{ticker} OR \"{company_name}\""
        
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
        - "BAC stock rises" -> TRUE (BAC is standalone word)
        - "Chelsea's backup system" -> FALSE (bac is part of backup)
        - "$MSFT earnings" -> TRUE (MSFT with symbol prefix)
        """
        if not text or not term:
            return False
        
        # Match term as complete word, not substring
        pattern = r'\b' + re.escape(term) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))
    
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
                print(f"Kept: {article.get('title', '')[:50]}")
                print(f"Score: {article['relevance_score']}")
            else:
                print(f"Dropped: {article.get('title', '')[:50]}")
                print(f"Score: {round(score, 2)} (below {threshold})")
        
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
            " Co", " limited", " Limited", " li", " nv", " sa", 
            " S.A.", " ag", " group", " holdings", " technologies", 
            " international", " incorporated", " inc", " inc.", 
            " plc", " PLC", ".com", " Platforms", " Group", " holdings"
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