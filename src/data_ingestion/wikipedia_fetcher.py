# src/data_ingestion/wikipedia_fetcher.py
"""Fetcher for Wikipedia pages using Wikipedia-API library"""

import wikipediaapi
from typing import Dict, Optional, Any, List
from datetime import datetime 

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data_ingestion.base_fetcher import BaseFetcher
from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class WikipediaFetcher(BaseFetcher):
    """
    Fetches Wikipedia pages using Wikipedia-API library
    
    Features:
    - Gets English Wikipedia pages only
    - Simpler interface than REST API
    - Automatic page resolution
    """
    
    def __init__(self):
        """Initialize Wikipedia fetcher"""
        super().__init__(rate_limit=200.0, max_retries=3)
        
        # Initialize Wikipedia-API client (English Wikipedia)
        self.wiki = wikipediaapi.Wikipedia(
            language='en',
            user_agent='DataPipeline/1.0 (Educational Project)'
        )
        
        logger.info("WikipediaFetcher initialized (Wikipedia-API library, English only)")
    
    def fetch(self, page_title: str) -> Dict[str, Any]:
        """
        Fetch Wikipedia page using Wikipedia-API library
        
        Args:
            page_title: Wikipedia page title (e.g., "Apple Inc.")
            
        Returns:
            Dict with page content and metadata
        """
        logger.info(f"Fetching Wikipedia page: {page_title}")
        
        # Fetch page using Wikipedia-API
        page = self.wiki.page(page_title)
        
        if not page.exists():
            raise ValueError(f"Wikipedia page not found: {page_title}")
        
        # Extract content
        result = {
            "page_title": page.title,
            "page_url": page.fullurl,
            "revision_id": page.pageid,  # Using page ID as revision tracking
            "summary": page.summary,
            "text_content": page.text,  # Full text content
            "html_content": self._text_to_html(page.text, page.title),  # Convert to simple HTML
            "sections": self._extract_sections(page),
            "categories": list(page.categories.keys()) if page.categories else [],
            "links": list(page.links.keys())[:50] if page.links else [],  # Limit to 50 links
            "language": page.language,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(
            f"Fetched Wikipedia: {page.title} "
            f"(ID: {page.pageid}, size: {len(page.text)} chars)"
        )
        
        return result
    
    def _extract_sections(self, page) -> List[Dict[str, str]]:
        """Extract sections from Wikipedia page"""
        sections = []
        
        def extract_recursive(section_obj, level=1):
            """Recursively extract sections"""
            for section in section_obj:
                sections.append({
                    "title": section.title,
                    "content": section.text,
                    "level": level
                })
                
                # Recursively get subsections
                if section.sections:
                    extract_recursive(section.sections, level + 1)
        
        if page.sections:
            extract_recursive(page.sections)
        
        return sections
    
    def _text_to_html(self, text: str, title: str) -> str:
        """Convert plain text to simple HTML"""
        html = f"<html><head><title>{title}</title></head><body>"
        html += f"<h1>{title}</h1>"
        
        # Convert text to paragraphs
        paragraphs = text.split('\n\n')
        for para in paragraphs:
            if para.strip():
                # Check if it's a heading (usually all caps or starts with ==)
                if para.strip().isupper() or para.startswith('=='):
                    html += f"<h2>{para.strip()}</h2>"
                else:
                    html += f"<p>{para.strip()}</p>"
        
        html += "</body></html>"
        return html
    
    def fetch_by_ticker(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch Wikipedia page by ticker
        
        Args:
            ticker: Company ticker
            
        Returns:
            Wikipedia page data (English only)
        """
        company = config.get_company_by_ticker(ticker)
        if not company:
            raise ValueError(f"Company {ticker} not found in config")
        
        # FIX: Use dot notation for dataclass (not dict notation)
        page_title = company.name  # ✅ FIXED: company.name not company['name']
        
        # Fetch from Wikipedia
        result = self.fetch_with_retry(page_title)
        
        # Add ticker to result
        result['ticker'] = ticker
        
        return result
    
    def get_page_id(self, page_title: str) -> int:
        """Get Wikipedia page ID (used as revision tracking)"""
        page = self.wiki.page(page_title)
        return page.pageid if page.exists() else 0
    
    def has_page_changed(self, page_title: str, stored_page_id: int) -> bool:
        """Check if page changed (using page ID as proxy)"""
        current_page_id = self.get_page_id(page_title)
        logger.info(f"Page ID for {page_title}: {current_page_id}")
        return True  # Always fetch for now (can optimize later with hash comparison)