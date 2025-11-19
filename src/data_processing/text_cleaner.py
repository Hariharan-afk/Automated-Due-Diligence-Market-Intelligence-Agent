# src/data_processing/text_cleaner.py
"""Text cleaning and normalization utilities"""

import re
from typing import Optional
from bs4 import BeautifulSoup
import unicodedata

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class TextCleaner:
    """
    Cleans and normalizes text from various sources
    
    Features:
    - HTML removal
    - Encoding normalization
    - Whitespace normalization
    - Language detection (English filtering)
    - Source-specific cleaning (Wikipedia, News)
    """
    
    def __init__(self):
        """Initialize text cleaner"""
        logger.info("TextCleaner initialized")
    
    def clean(
        self,
        text: str,
        source_type: str = "generic",
        remove_html: bool = True,
        normalize_whitespace: bool = True,
        fix_encoding: bool = True,
        verify_english: bool = True
    ) -> Optional[str]:
        """
        Clean text (PRODUCTION-READY)
        
        Args:
            text: Raw text to clean
            source_type: "wikipedia", "news", or "generic"
            remove_html: Remove HTML tags
            normalize_whitespace: Normalize spaces/newlines
            fix_encoding: Fix encoding issues
            verify_english: Verify text is English (returns None if not)
            
        Returns:
            Cleaned text or None if non-English
        """
        if not text:
            return ""
        
        cleaned = text
        
        # Remove HTML
        if remove_html:
            cleaned = self.remove_html(cleaned)
        
        # Fix encoding
        if fix_encoding:
            cleaned = self.fix_encoding(cleaned)
        
        # Language check
        if verify_english:
            if not self.is_english_text(cleaned):
                logger.warning("Text is not English - returning None")
                return None
        
        # Source-specific cleaning
        if source_type == "wikipedia":
            cleaned = self.clean_wikipedia_specific(cleaned)
        elif source_type == "news":
            cleaned = self.clean_news_specific(cleaned)
        
        # Normalize whitespace
        if normalize_whitespace:
            cleaned = self.normalize_whitespace(cleaned)
        
        # Remove non-printable
        cleaned = self.remove_non_printable(cleaned)
        
        return cleaned.strip()
    
    @staticmethod
    def remove_html(text: str) -> str:
        """Remove HTML tags (PRODUCTION-READY)"""
        soup = BeautifulSoup(text, 'html.parser')
        
        for element in soup(["script", "style", "meta", "link", "noscript"]):
            element.decompose()
        
        return soup.get_text()
    
    @staticmethod
    def fix_encoding(text: str) -> str:
        """Fix encoding issues (PRODUCTION-READY)"""
        replacements = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&apos;': "'",
            '&#8217;': "'",
            '&#8216;': "'",
            '&#8220;': '"',
            '&#8221;': '"',
            '&#8211;': '-',
            '&#8212;': '—',
            '&mdash;': '—',
            '&ndash;': '–',
            '&rsquo;': "'",
            '&lsquo;': "'",
            '&rdquo;': '"',
            '&ldquo;': '"',
        }
        
        for entity, char in replacements.items():
            text = text.replace(entity, char)
        
        text = unicodedata.normalize('NFKD', text)
        
        return text
    
    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Normalize whitespace (PRODUCTION-READY)"""
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        text = text.replace('\t', ' ')
        
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)
        
        return text
    
    @staticmethod
    def remove_non_printable(text: str) -> str:
        """Remove non-printable characters (PRODUCTION-READY)"""
        cleaned = ''.join(
            char for char in text 
            if char.isprintable() or char in ['\n', '\t']
        )
        return cleaned
    
    @staticmethod
    def clean_wikipedia_specific(text: str) -> str:
        """Wikipedia-specific cleaning (PRODUCTION-READY)"""
        text = re.sub(r'\[\d+\]', '', text)
        text = re.sub(r'\[citation needed\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[edit\]', '', text)
        
        text = re.sub(
            r'\n(See also|References|External links|Notes|Further reading|Bibliography).*$',
            '',
            text,
            flags=re.IGNORECASE | re.DOTALL
        )
        
        text = re.sub(r'\{\{[^}]+\}\}', '', text)
        text = re.sub(r'\([^)]*pronunciation[^)]*\)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\d+°\d+′\d+″[NS]\s+\d+°\d+′\d+″[EW]', '', text)
        
        return text
    
    @staticmethod
    def clean_news_specific(text: str) -> str:
        """News-specific cleaning (PRODUCTION-READY)"""
        boilerplate = [
            r'Subscribe to.*?newsletter',
            r'Sign up for.*?updates',
            r'Follow us on.*',
            r'Share this article',
            r'Related articles:.*$',
            r'Advertisement',
            r'ADVERTISEMENT',
            r'Click here to.*$',
            r'Read more:.*$',
            r'Copyright \d{4}.*$',
            r'All rights reserved',
            r'Terms of Service',
            r'Privacy Policy'
        ]
        
        for pattern in boilerplate:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
        
        text = re.sub(r'http[s]?://\S+', '', text)
        text = re.sub(r'\S+@\S+', '', text)
        text = re.sub(r'@\w+', '', text)
        text = re.sub(r'#\w+', '', text)
        
        return text
    
    def is_english_text(self, text: str, threshold: float = 0.7) -> bool:
        """
        Detect if text is English (PRODUCTION-READY)
        
        Args:
            text: Text to check
            threshold: Minimum English word ratio (0.7 = 70%)
            
        Returns:
            True if English
        """
        if not text or len(text) < 50:
            return False
        
        sample = text[:500].lower()
        
        common_english = {
            'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have',
            'i', 'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you',
            'do', 'at', 'this', 'but', 'his', 'by', 'from', 'they',
            'we', 'say', 'her', 'she', 'or', 'an', 'will', 'my', 'one',
            'all', 'would', 'there', 'their', 'what', 'so', 'up', 'out',
            'if', 'about', 'who', 'get', 'which', 'go', 'me', 'when',
            'make', 'can', 'like', 'time', 'no', 'just', 'him', 'know',
            'take', 'people', 'into', 'year', 'your', 'good', 'some',
            'could', 'them', 'see', 'other', 'than', 'then', 'now',
            'look', 'only', 'come', 'its', 'over', 'think', 'also',
            'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first',
            'well', 'way', 'even', 'new', 'want', 'because', 'any',
            'these', 'give', 'day', 'most', 'us', 'is', 'was', 'are',
            'been', 'has', 'had', 'were', 'said', 'did', 'may', 'such'
        }
        
        words = re.findall(r'\b[a-z]+\b', sample)
        
        if not words:
            return False
        
        english_count = sum(1 for word in words if word in common_english)
        ratio = english_count / len(words)
        
        is_english = ratio >= threshold
        
        if not is_english:
            logger.debug(f"Non-English detected: {ratio:.1%} English words")
        
        return is_english