# src/data_processing/news_parser.py
"""Parser for news article structure"""

from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
import re

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class NewsParser:
    """
    Parses news articles to extract clean content
    
    Features:
    - Extracts article body (excludes ads, navigation)
    - Identifies title, author, date
    - Removes boilerplate and clutter
    - Handles various news site structures
    """
    
    def __init__(self):
        """Initialize news parser"""
        logger.info("NewsParser initialized")
    
    def parse(
        self,
        html_content: str,
        article_url: str,
        article_title: Optional[str] = None,
        published_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse news article HTML (PRODUCTION-READY)
        
        Args:
            html_content: Raw HTML content
            article_url: Article URL
            article_title: Pre-extracted title (from fetcher)
            published_date: Pre-extracted date (from fetcher)
            
        Returns:
            Parsed article dict with clean content
        """
        logger.info(f"Parsing news article: {article_url[:60]}...")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Use provided title or extract
        title = article_title or self._extract_title(soup)
        
        # Extract article body
        body = self._extract_article_body(soup)
        
        # Use provided date or extract
        pub_date = published_date or self._extract_date(soup)
        
        # Extract author
        author = self._extract_author(soup)
        
        result = {
            "title": title,
            "body": body,
            "author": author,
            "published_date": pub_date,
            "url": article_url,
            "word_count": len(body.split()) if body else 0
        }
        
        logger.info(
            f"Parsed article: '{title[:50]}...' ({result['word_count']} words)"
        )
        
        return result
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract article title (PRODUCTION-READY)"""
        # Method 1: <title> tag
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
            # Remove site name
            title = re.split(r'\s+[-|]\s+', title)[0]
            return title
        
        # Method 2: h1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()
        
        # Method 3: og:title
        og_title = soup.find('meta', {'property': 'og:title'})
        if og_title and og_title.get('content'):
            return og_title['content'].strip()
        
        return "Unknown Title"
    
    def _extract_article_body(self, soup: BeautifulSoup) -> str:
        """Extract article body (PRODUCTION-READY)"""
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'form']):
            element.decompose()
        
        # Try common article selectors
        selectors = [
            ('article', {}),
            ('div', {'class': re.compile(r'article|content|post|entry|story', re.I)}),
            ('div', {'id': re.compile(r'article|content|post|entry|story', re.I)}),
            ('main', {}),
            ('div', {'role': 'main'})
        ]
        
        article_content = None
        
        for tag, attrs in selectors:
            article_content = soup.find(tag, attrs)
            if article_content:
                break
        
        # Fallback
        if not article_content:
            article_content = soup.find('body') or soup
        
        # Extract paragraphs
        paragraphs = article_content.find_all('p')
        
        # Filter out short paragraphs (likely not article content)
        body_paragraphs = [
            p.get_text().strip() 
            for p in paragraphs 
            if len(p.get_text().strip()) > 50  # At least 50 chars
        ]
        
        body_text = '\n\n'.join(body_paragraphs)
        
        return body_text
    
    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract author (PRODUCTION-READY)"""
        # Meta author
        author_meta = soup.find('meta', {'name': 'author'})
        if author_meta and author_meta.get('content'):
            return author_meta['content'].strip()
        
        # By-line class
        byline = soup.find(class_=re.compile(r'author|byline|writer', re.I))
        if byline:
            return byline.get_text().strip()
        
        # rel="author"
        author_link = soup.find('a', {'rel': 'author'})
        if author_link:
            return author_link.get_text().strip()
        
        return None
    
    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract publication date (PRODUCTION-READY)"""
        # time tag
        time_tag = soup.find('time')
        if time_tag and time_tag.get('datetime'):
            return time_tag['datetime']
        
        # article:published_time
        pub_meta = soup.find('meta', {'property': 'article:published_time'})
        if pub_meta and pub_meta.get('content'):
            return pub_meta['content']
        
        # datePublished
        date_meta = soup.find('meta', {'itemprop': 'datePublished'})
        if date_meta and date_meta.get('content'):
            return date_meta['content']
        
        return None
    
    def parse_simple(
        self,
        text: str,
        title: str,
        published_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Simple parsing for plain text articles (PRODUCTION-READY)
        
        Use when you already have clean text (not HTML)
        
        Args:
            text: Plain article text
            title: Article title
            published_date: Publication date
            
        Returns:
            Parsed article dict
        """
        return {
            "title": title,
            "body": text,
            "author": None,
            "published_date": published_date,
            "word_count": len(text.split())
        }