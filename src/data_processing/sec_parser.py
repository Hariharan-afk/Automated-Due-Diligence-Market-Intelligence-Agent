# src/data_processing/sec_parser.py
"""Parser for SEC filing HTML using MarkItDown"""

from typing import Dict, List, Any, Optional
from markitdown import MarkItDown
import re
import tempfile
import os

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SECParser:
    """
    Parses SEC filing HTML to Markdown
    
    Features:
    - Converts HTML to Markdown using MarkItDown
    - Splits by horizontal lines (---) 
    - Preserves table structures
    - Extracts section metadata
    """
    
    def __init__(self):
        """Initialize SEC parser"""
        self.markitdown = MarkItDown()
        logger.info("SECParser initialized (MarkItDown)")
    
    def parse_filing_section(
        self,
        html_content: str,
        section_code: str,
        section_name: str,
        filing_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse a SEC filing section from HTML to Markdown
        
        Args:
            html_content: Raw HTML content
            section_code: Section code (e.g., "1", "1A", "8")
            section_name: Section name (e.g., "Business")
            filing_metadata: Metadata about the filing (ticker, year, etc.)
        
        Returns:
            Dict with:
                - markdown_content: Full markdown text
                - chunks: List of text chunks (split by ---)
                - section_code: Section code
                - section_name: Section name
                - metadata: Filing metadata
        """
        logger.info(f"Parsing section {section_code}: {section_name}")
        
        # Convert HTML to Markdown using MarkItDown
        markdown_content = self._html_to_markdown(html_content)
        
        # Split by horizontal lines (---)
        chunks = self._split_by_horizontal_lines(markdown_content)
        
        logger.info(f"Parsed section {section_code}: {len(chunks)} chunks, "
                   f"{len(markdown_content)} chars")
        
        return {
            'markdown_content': markdown_content,
            'chunks': chunks,
            'section_code': section_code,
            'section_name': section_name,
            'metadata': filing_metadata,
            'chunk_count': len(chunks)
        }
    
    def _html_to_markdown(self, html_content: str) -> str:
        """
        Convert HTML to Markdown using MarkItDown
        
        MarkItDown requires a file path, not HTML content string.
        So we save to a temp file first.
        
        Args:
            html_content: Raw HTML string
        
        Returns:
            Markdown text
        """
        temp_file = None
        
        try:
            # Create a temporary HTML file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.html',
                delete=False,
                encoding='utf-8'
            ) as f:
                f.write(html_content)
                temp_file = f.name
            
            # Convert using MarkItDown (pass file path)
            result = self.markitdown.convert(temp_file)
            
            # Extract text content
            # MarkItDown returns a DocumentConverterResult object with text_content attribute
            markdown = result.text_content if hasattr(result, 'text_content') else str(result)
            
            # Clean up markdown
            markdown = self._clean_markdown(markdown)
            
            return markdown
            
        except Exception as e:
            logger.error(f"Failed to convert HTML to Markdown: {e}")
            # Fallback: return raw HTML
            return html_content
            
        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_file}: {e}")
    
    def _clean_markdown(self, markdown: str) -> str:
        """Clean up converted markdown"""
        # Remove excessive newlines (more than 3 consecutive)
        markdown = re.sub(r'\n{4,}', '\n\n\n', markdown)
        
        # Remove leading/trailing whitespace from each line
        lines = markdown.split('\n')
        lines = [line.rstrip() for line in lines]
        markdown = '\n'.join(lines)
        
        return markdown.strip()
    
    def _split_by_horizontal_lines(self, markdown: str) -> List[str]:
        """
        Split markdown by horizontal lines (---)
        
        Horizontal lines in markdown:
        - ---
        - ***
        - ___
        
        Args:
            markdown: Markdown text
        
        Returns:
            List of text chunks
        """
        # Pattern for horizontal lines
        # Must be on its own line with optional whitespace
        hr_pattern = r'^\s*[-_*]{3,}\s*$'
        
        lines = markdown.split('\n')
        chunks = []
        current_chunk = []
        
        for line in lines:
            # Check if line is a horizontal rule
            if re.match(hr_pattern, line):
                # Save current chunk if not empty
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk).strip()
                    if chunk_text:
                        chunks.append(chunk_text)
                    current_chunk = []
                continue
            
            current_chunk.append(line)
        
        # Add last chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk).strip()
            if chunk_text:
                chunks.append(chunk_text)
        
        logger.debug(f"Split markdown into {len(chunks)} chunks by horizontal lines")
        
        return chunks
    
    def parse_multiple_sections(
        self,
        sections_html: Dict[str, str],
        section_names: Dict[str, str],
        filing_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Parse multiple sections from a filing
        
        Args:
            sections_html: Dict mapping section_code -> HTML content
            section_names: Dict mapping section_code -> section name
            filing_metadata: Filing metadata
        
        Returns:
            List of parsed section dicts
        """
        parsed_sections = []
        
        for section_code, html_content in sections_html.items():
            section_name = section_names.get(section_code, f"Section {section_code}")
            
            parsed = self.parse_filing_section(
                html_content=html_content,
                section_code=section_code,
                section_name=section_name,
                filing_metadata=filing_metadata
            )
            
            parsed_sections.append(parsed)
        
        logger.info(f"Parsed {len(parsed_sections)} sections from filing")
        
        return parsed_sections