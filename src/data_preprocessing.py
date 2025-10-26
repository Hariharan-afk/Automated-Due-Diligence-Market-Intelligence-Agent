"""
Data Preprocessing Module - FINAL VERSION
Handles data cleaning, transformation, and validation
"""

import pandas as pd
import json
import logging
import re
from typing import Dict, List, Any
from datetime import datetime
import os
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataCleaner:
    """Clean and normalize raw data"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Remove special characters and normalize text"""
        if not text or text == "N/A":
            return ""
        
        # Remove HTML tags
        text = BeautifulSoup(text, "html.parser").get_text()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\;]', '', text)
        
        return text
    
    @staticmethod
    def clean_url(url: str) -> str:
        """Validate and clean URLs"""
        if not url or url == "N/A":
            return ""
        
        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        return url.strip()
    
    @staticmethod
    def parse_date(date_str: str) -> str:
        """Standardize date format"""
        if not date_str or date_str == "N/A":
            return ""
        
        try:
            # Try parsing ISO format
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        except:
            try:
                # Try GDELT format (YYYYMMDDHHMMSS)
                if len(date_str) >= 8 and date_str.isdigit():
                    dt = datetime.strptime(date_str[:8], '%Y%m%d')
                    return dt.strftime('%Y-%m-%d')
            except:
                pass
        
        logger.warning(f"Could not parse date: {date_str}")
        return date_str
    
    @staticmethod
    def remove_duplicates(items: List[Dict], key: str = 'url') -> List[Dict]:
        """Remove duplicate items based on key"""
        seen = set()
        unique_items = []
        
        for item in items:
            identifier = item.get(key, '')
            if identifier and identifier not in seen:
                seen.add(identifier)
                unique_items.append(item)
        
        return unique_items


class WikipediaPreprocessor:
    """Preprocess Wikipedia data"""
    
    def __init__(self):
        self.cleaner = DataCleaner()
    
    def process(self, wiki_data: Dict) -> Dict:
        """Process Wikipedia data"""
        if "error" in wiki_data:
            return wiki_data
        
        processed = {
            "title": wiki_data.get("title", ""),
            "summary": self.cleaner.clean_text(wiki_data.get("summary", "")),
            "full_text": self.cleaner.clean_text(wiki_data.get("full_text", "")),
            "url": self.cleaner.clean_url(wiki_data.get("url", "")),
            "word_count": len(wiki_data.get("full_text", "").split()),
            "section_count": len(wiki_data.get("sections", [])),
            "has_infobox": self._check_infobox(wiki_data.get("full_text", "")),
            "timestamp": wiki_data.get("timestamp", "")
        }
        
        return processed
    
    @staticmethod
    def _check_infobox(text: str) -> bool:
        """Check if Wikipedia page has infobox"""
        return "infobox" in text.lower() or "founded" in text.lower()


class NewsPreprocessor:
    """Preprocess news articles"""
    
    def __init__(self):
        self.cleaner = DataCleaner()
    
    def process(self, news_articles: List[Dict]) -> List[Dict]:
        """Process news articles"""
        # Remove duplicates
        articles = self.cleaner.remove_duplicates(news_articles)
        
        processed_articles = []
        for article in articles:
            processed = {
                "title": self.cleaner.clean_text(article.get("title", "")),
                "url": self.cleaner.clean_url(article.get("url", "")),
                "source": article.get("source", "Unknown"),
                "published_date": self.cleaner.parse_date(article.get("published_date", "")),
                "description": self.cleaner.clean_text(article.get("description", "")),
                "content": self.cleaner.clean_text(article.get("content", "")),
                "word_count": len(article.get("content", "").split()),
                "has_content": bool(article.get("content", ""))
            }
            
            # Filter out low-quality articles
            if self._is_valid_article(processed):
                processed_articles.append(processed)
        
        return processed_articles
    
    @staticmethod
    def _is_valid_article(article: Dict) -> bool:
        """Validate article quality"""
        # Must have title and URL
        if not article.get("title") or not article.get("url"):
            return False
        
        # Filter out removed/unavailable articles
        if "[Removed]" in article.get("title", ""):
            return False
        
        return True


class DataPreprocessingPipeline:
    """Main preprocessing pipeline"""
    
    def __init__(self):
        self.wiki_processor = WikipediaPreprocessor()
        self.news_processor = NewsPreprocessor()
    
    def process_company_data(self, raw_data: Dict) -> Dict:
        """
        Process all company data
        
        Args:
            raw_data: Raw data from acquisition pipeline
            
        Returns:
            Processed and validated data
        """
        logger.info(f"🔄 Processing data for: {raw_data.get('company_name')}")
        
        # Process Wikipedia data
        wiki_processed = self.wiki_processor.process(raw_data.get("wikipedia", {}))
        
        # Process news articles
        news_processed = self.news_processor.process(raw_data.get("news_articles", []))
        
        # Compile processed data
        processed_data = {
            "query": raw_data.get("query"),
            "ticker": raw_data.get("ticker"),
            "company_name": raw_data.get("company_name"),
            "cik": raw_data.get("cik"),
            "wikipedia": wiki_processed,
            "news_articles": news_processed,
            "statistics": {
                "total_news_articles": len(news_processed),
                "wikipedia_word_count": wiki_processed.get("word_count", 0),
                "news_sources": list(set(article.get("source", "") for article in news_processed)),
                "date_range": self._get_date_range(news_processed)
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Save processed data
        self._save_processed_data(processed_data)
        
        logger.info(f"✅ Processing complete for: {raw_data.get('company_name')}")
        return processed_data
    
    @staticmethod
    def _get_date_range(articles: List[Dict]) -> Dict:
        """Get date range of articles"""
        dates = [article.get("published_date", "") for article in articles if article.get("published_date")]
        
        if not dates:
            return {"earliest": None, "latest": None}
        
        valid_dates = sorted([d for d in dates if d])
        return {
            "earliest": valid_dates[0] if valid_dates else None,
            "latest": valid_dates[-1] if valid_dates else None
        }
    
    @staticmethod
    def _save_processed_data(data: Dict):
        """Save processed data to file"""
        os.makedirs("data/processed", exist_ok=True)
        filename = f"data/processed/{data['company_name'].replace(' ', '_')}_processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        logger.info(f"💾 Processed data saved to: {filename}")


def main():
    """Example usage"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python data_preprocessing.py <raw_data_file.json>")
        sys.exit(1)
    
    raw_file = sys.argv[1]
    
    if os.path.exists(raw_file):
        with open(raw_file, 'r') as f:
            raw_data = json.load(f)
        
        pipeline = DataPreprocessingPipeline()
        processed_data = pipeline.process_company_data(raw_data)
        
        print(f"\n{'='*50}")
        print(f"Processed: {processed_data['company_name']}")
        print(f"Wikipedia Words: {processed_data['statistics']['wikipedia_word_count']}")
        print(f"News Articles: {processed_data['statistics']['total_news_articles']}")
        print(f"{'='*50}\n")
    else:
        print(f"File not found: {raw_file}")
        sys.exit(1)


if __name__ == "__main__":
    main()