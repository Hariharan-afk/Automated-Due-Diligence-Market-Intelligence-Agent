# src/data_processing/wikipedia_parser.py
"""Parser for Wikipedia page HTML structure"""

from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
import re

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class WikipediaParser:
    """
    Parses Wikipedia page HTML to extract structured content
    
    Features:
    - Extracts main content (excludes navigation, footer)
    - Identifies sections
    - Separates intro from body
    - Removes Wikipedia-specific elements
    - Handles infoboxes and tables
    """
    
    def __init__(self):
        """Initialize Wikipedia parser"""
        logger.info("WikipediaParser initialized")
    
    def parse(self, html_content: str, page_title: str) -> Dict[str, Any]:
        """
        Parse Wikipedia HTML page (PRODUCTION-READY)
        
        Args:
            html_content: Raw Wikipedia HTML
            page_title: Page title for context
            
        Returns:
            Parsed content dict with sections
        """
        logger.info(f"Parsing Wikipedia page: {page_title}")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract main content
        main_content = self._extract_main_content(soup)
        
        # Extract intro (text before first section header)
        intro = self._extract_intro(main_content)
        
        # Extract sections
        sections = self._extract_sections(main_content)
        
        # Extract infobox data (optional metadata)
        infobox = self._extract_infobox(soup)
        
        result = {
            "page_title": page_title,
            "intro": intro,
            "sections": sections,
            "infobox": infobox,
            "total_sections": len(sections)
        }
        
        logger.info(
            f"Parsed {page_title}: intro + {len(sections)} sections"
        )
        
        return result
    
    def _extract_main_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Extract main content area (PRODUCTION-READY)"""
        # Wikipedia main content is typically in specific div/section
        # Try common selectors
        main_selectors = [
            {'id': 'mw-content-text'},
            {'class': 'mw-parser-output'},
            {'role': 'main'}
        ]
        
        for selector in main_selectors:
            main = soup.find('div', selector) or soup.find('section', selector)
            if main:
                return main
        
        # Fallback: use entire body
        return soup
    
    def _extract_intro(self, content: BeautifulSoup) -> str:
        """
        Extract introduction/lead section (PRODUCTION-READY)
        
        The intro is all text before the first heading
        """
        intro_parts = []
        
        # Get all direct children
        for element in content.children:
            # Stop at first heading
            if element.name and element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                break
            
            # Skip infobox and other non-content
            if element.name == 'table':
                continue
            
            # Get text from paragraphs
            if element.name == 'p':
                text = element.get_text()
                if text.strip():
                    intro_parts.append(text)
        
        intro = ' '.join(intro_parts)
        
        logger.debug(f"Extracted intro: {len(intro)} characters")
        
        return intro.strip()
    
    def _extract_sections(self, content: BeautifulSoup) -> List[Dict[str, str]]:
        """
        Extract sections with headings (PRODUCTION-READY)
        
        Returns list of {title, content} dicts
        """
        sections = []
        current_section = None
        current_content = []
        
        for element in content.find_all(['h2', 'h3', 'h4', 'p', 'ul', 'ol']):
            # New section header
            if element.name in ['h2', 'h3', 'h4']:
                # Save previous section
                if current_section:
                    sections.append({
                        'title': current_section,
                        'level': current_level,
                        'content': ' '.join(current_content)
                    })
                
                # Start new section
                current_section = element.get_text().strip()
                current_level = element.name
                current_content = []
            
            # Content within section
            elif current_section:
                text = element.get_text().strip()
                if text:
                    current_content.append(text)
        
        # Add last section
        if current_section and current_content:
            sections.append({
                'title': current_section,
                'level': current_level,
                'content': ' '.join(current_content)
            })
        
        logger.debug(f"Extracted {len(sections)} sections")
        
        return sections
    
    def _extract_infobox(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Extract infobox data (PRODUCTION-READY)
        
        Infobox contains structured company info
        """
        infobox_data = {}
        
        # Find infobox (usually has class 'infobox')
        infobox = soup.find('table', {'class': re.compile(r'infobox', re.I)})
        
        if not infobox:
            return infobox_data
        
        # Extract key-value pairs from table rows
        for row in infobox.find_all('tr'):
            header = row.find('th')
            data = row.find('td')
            
            if header and data:
                key = header.get_text().strip()
                value = data.get_text().strip()
                
                # Clean value (remove citations)
                value = re.sub(r'\[\d+\]', '', value)
                
                infobox_data[key] = value
        
        logger.debug(f"Extracted {len(infobox_data)} infobox fields")
        
        return infobox_data
    
    def get_all_text(self, parsed_content: Dict[str, Any]) -> str:
        """
        Get all text combined (PRODUCTION-READY)
        
        Args:
            parsed_content: Result from parse()
            
        Returns:
            All text combined (intro + all sections)
        """
        all_text = []
        
        # Add intro
        if parsed_content.get('intro'):
            all_text.append(parsed_content['intro'])
        
        # Add all sections
        for section in parsed_content.get('sections', []):
            all_text.append(section['content'])
        
        combined = '\n\n'.join(all_text)
        
        return combined