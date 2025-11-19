# src/data_processing/metadata_enricher.py
"""Adds metadata to text chunks for tracking and filtering"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import hashlib

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class MetadataEnricher:
    """
    Enriches text chunks with comprehensive metadata
    
    Adds:
    - Unique chunk IDs
    - Source information (ticker, company, filing type)
    - Temporal information (dates, fiscal periods)
    - Structural information (section, position)
    - Statistical information (word count, token count)
    """
    
    def __init__(self):
        """Initialize metadata enricher"""
        logger.info("MetadataEnricher initialized")
    
    def enrich_chunk(
        self,
        chunk_text: str,
        source_metadata: Dict[str, Any],
        position: int = 0,
        chunk_type: str = "text"
    ) -> Dict[str, Any]:
        """
        Enrich a single chunk with metadata (PRODUCTION-READY)
        
        Args:
            chunk_text: The chunk text
            source_metadata: Source document metadata (ticker, filing_type, etc.)
            position: Chunk position in document
            chunk_type: "text" or "table"
            
        Returns:
            Enriched chunk dict with text and metadata
        """
        # Generate unique chunk ID
        chunk_id = self.generate_chunk_id(source_metadata, position, chunk_type)
        
        # Calculate statistics
        word_count = len(chunk_text.split())
        
        # Build enriched chunk
        enriched = {
            "chunk_id": chunk_id,
            "text": chunk_text,
            "chunk_type": chunk_type,
            "position": position,
            "word_count": word_count,
            "created_at": datetime.now().isoformat(),
            "metadata": {
                **source_metadata,
                "chunk_position": position,
                "chunk_type": chunk_type
            }
        }
        
        return enriched
    
    def enrich_chunks(
        self,
        chunks: List[str],
        source_metadata: Dict[str, Any],
        chunk_type: str = "text"
    ) -> List[Dict[str, Any]]:
        """
        Enrich multiple chunks (PRODUCTION-READY)
        
        Args:
            chunks: List of chunk texts
            source_metadata: Source metadata
            chunk_type: "text" or "table"
            
        Returns:
            List of enriched chunks
        """
        enriched_chunks = []
        
        for i, chunk_text in enumerate(chunks):
            enriched = self.enrich_chunk(
                chunk_text=chunk_text,
                source_metadata=source_metadata,
                position=i,
                chunk_type=chunk_type
            )
            enriched_chunks.append(enriched)
        
        logger.info(f"Enriched {len(enriched_chunks)} chunks with metadata")
        
        return enriched_chunks
    
    @staticmethod
    def generate_chunk_id(
        source_metadata: Dict[str, Any],
        position: int,
        chunk_type: str
    ) -> str:
        """
        Generate unique chunk ID (PRODUCTION-READY)
        
        Format for SEC: TICKER_FILINGTYPE_YEAR_SECTION_TYPE_POSITION
        Format for Wikipedia: TICKER_WIKI_REVISION_TYPE_POSITION
        Format for News: TICKER_NEWS_DATE_ARTICLEID_TYPE_POSITION
        
        Args:
            source_metadata: Source metadata dict
            position: Chunk position
            chunk_type: "text" or "table"
            
        Returns:
            Unique chunk ID string
        """
        ticker = source_metadata.get('ticker', 'UNK')
        source_type = source_metadata.get('source_type', 'unknown')
        
        if source_type == 'sec_filing':
            # SEC format: AAPL_10K_2024_1A_text_001
            filing_type = source_metadata.get('filing_type', 'UNK')
            fiscal_year = source_metadata.get('fiscal_year', '0000')
            section = source_metadata.get('section', 'UNK')
            
            chunk_id = f"{ticker}_{filing_type}_{fiscal_year}_{section}_{chunk_type}_{position:03d}"
        
        elif source_type == 'wikipedia':
            # Wikipedia format: AAPL_WIKI_1234567890_text_001
            revision_id = source_metadata.get('revision_id', '0')
            
            chunk_id = f"{ticker}_WIKI_{revision_id}_{chunk_type}_{position:03d}"
        
        elif source_type == 'news':
            # News format: AAPL_NEWS_20241117_abc123_text_001
            pub_date = source_metadata.get('published_date', datetime.now())
            if isinstance(pub_date, str):
                date_str = pub_date[:10].replace('-', '')
            else:
                date_str = pub_date.strftime('%Y%m%d')
            
            # Generate article hash for uniqueness
            article_url = source_metadata.get('article_url', '')
            article_hash = hashlib.md5(article_url.encode()).hexdigest()[:8]
            
            chunk_id = f"{ticker}_NEWS_{date_str}_{article_hash}_{chunk_type}_{position:03d}"
        
        else:
            # Generic format
            chunk_id = f"{ticker}_GENERIC_{chunk_type}_{position:03d}"
        
        return chunk_id
    
    @staticmethod
    def create_source_metadata_wikipedia(
        ticker: str,
        page_title: str,
        revision_id: int,
        page_url: str,
        section: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create source metadata for Wikipedia (PRODUCTION-READY)
        
        Args:
            ticker: Company ticker
            page_title: Wikipedia page title
            revision_id: Wikipedia revision ID
            page_url: Wikipedia page URL
            section: Optional section name
            
        Returns:
            Metadata dict
        """
        company = config.get_company_by_ticker(ticker)
        
        metadata = {
            "source_type": "wikipedia",
            "ticker": ticker,
            "company_name": company['name'] if company else ticker,
            "page_title": page_title,
            "revision_id": revision_id,
            "page_url": page_url,
            "section": section or "main"
        }
        
        return metadata
    
    @staticmethod
    def create_source_metadata_news(
        ticker: str,
        article_url: str,
        article_title: str,
        published_date: datetime,
        source: str,
        article_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create source metadata for news (PRODUCTION-READY)
        
        Args:
            ticker: Company ticker
            article_url: Article URL
            article_title: Article title
            published_date: Publication date
            source: News source domain
            article_id: Optional article ID from database
            
        Returns:
            Metadata dict
        """
        company = config.get_company_by_ticker(ticker)
        
        metadata = {
            "source_type": "news",
            "ticker": ticker,
            "company_name": company['name'] if company else ticker,
            "article_url": article_url,
            "article_title": article_title,
            "published_date": published_date.isoformat() if isinstance(published_date, datetime) else published_date,
            "source": source,
            "article_id": article_id
        }
        
        return metadata
    
    @staticmethod
    def create_source_metadata_sec(
        ticker: str,
        filing_type: str,
        filing_date: str,
        fiscal_year: int,
        accession_number: str,
        section: str,
        filing_url: str,
        fiscal_quarter: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create source metadata for SEC (PRODUCTION-READY)
        
        Args:
            ticker: Company ticker
            filing_type: Filing type (10-K, 10-Q)
            filing_date: Filing date
            fiscal_year: Fiscal year
            accession_number: SEC accession number
            section: Section code
            filing_url: Filing URL
            fiscal_quarter: Fiscal quarter (for 10-Q)
            
        Returns:
            Metadata dict
        """
        company = config.get_company_by_ticker(ticker)
        
        metadata = {
            "source_type": "sec_filing",
            "ticker": ticker,
            "company_name": company['name'] if company else ticker,
            "filing_type": filing_type,
            "filing_date": filing_date,
            "fiscal_year": fiscal_year,
            "fiscal_quarter": fiscal_quarter,
            "accession_number": accession_number,
            "section": section,
            "filing_url": filing_url
        }
        
        return metadata


