# src/data_processing/wikipedia_processor.py
"""Wikipedia page processor"""

from typing import Dict, Any
from datetime import datetime
import hashlib

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data_ingestion.wikipedia_fetcher import WikipediaFetcher
from src.data_processing.wikipedia_parser import WikipediaParser
from src.data_processing.chunker import TextChunker
from src.data_processing.embedder import FinancialEmbedder
from src.storage.postgres_manager import PostgresManager
from src.storage.qdrant_manager import QdrantManager
from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class WikipediaProcessor:
    """
    Orchestrates Wikipedia page processing workflow
    
    Workflow:
    1. Fetch Wikipedia page
    2. Parse HTML → structured content
    3. Check if content changed (revision ID)
    4. If changed: delete old chunks, process new
    5. Chunk text
    6. Embed chunks
    7. Store in Qdrant + PostgreSQL
    """
    
    def __init__(
        self,
        postgres_manager: PostgresManager,
        qdrant_manager: QdrantManager,
        embedder: FinancialEmbedder
    ):
        """
        Initialize Wikipedia processor
        
        Args:
            postgres_manager: PostgreSQL manager instance
            qdrant_manager: Qdrant manager instance
            embedder: Embedder instance
        """
        self.postgres = postgres_manager
        self.qdrant = qdrant_manager
        self.embedder = embedder
        
        # Initialize components
        self.fetcher = WikipediaFetcher()
        self.parser = WikipediaParser()
        self.chunker = TextChunker(chunk_size=800, overlap=100)
        
        logger.info("WikipediaProcessor initialized")
    
    def process_page(self, ticker: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Process Wikipedia page for a company
        
        Args:
            ticker: Company ticker
            force_refresh: Force re-processing even if not changed
        
        Returns:
            Processing result dict
        """
        logger.info(f"Processing Wikipedia page for {ticker}")
        
        # Get company info
        company = config.get_company_by_ticker(ticker)
        if not company:
            raise ValueError(f"Company {ticker} not found")
        
        # Check if page exists in DB and if it changed
        existing_page = self.postgres.get_wikipedia_page(ticker)
        
        # Fetch current page
        try:
            page_data = self.fetcher.fetch_by_ticker(ticker)
        except Exception as e:
            logger.error(f"Failed to fetch Wikipedia page for {ticker}: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
        
        # Check if content changed
        current_revision = page_data.get('revision_id')
        content_hash = self._hash_content(page_data.get('text_content', ''))
        
        if existing_page and not force_refresh:
            if (existing_page['revision_id'] == current_revision or 
                existing_page['content_hash'] == content_hash):
                logger.info(f"Wikipedia page for {ticker} hasn't changed, skipping")
                return {
                    'status': 'skipped',
                    'reason': 'no_changes',
                    'revision_id': current_revision
                }
        
        # Page changed or force refresh - process it
        try:
            # Parse HTML content
            parsed = self.parser.parse(
                html_content=page_data.get('html_content', ''),
                page_title=page_data['page_title']
            )
            
            # Get all text
            full_text = self.parser.get_all_text(parsed)
            
            # Chunk text
            chunks = self.chunker.chunk_text(full_text, preserve_tables=True)
            total_chunks = len(chunks)
            
            logger.info(f"Chunked Wikipedia into {total_chunks} chunks")
            
            # Embed chunks
            embeddings = self.embedder.embed_chunks(chunks, show_progress=True)
            
            # Construct GCS path
            gcs_path = f"raw/wikipedia/{ticker}/{page_data['page_title'].replace(' ', '_')}.json"
            
            # Get timestamps
            current_time = datetime.utcnow().isoformat() + 'Z'
            last_modified = page_data.get('timestamp') or page_data.get('last_modified')
            if last_modified and not last_modified.endswith('Z'):
                last_modified += 'Z'
            
            # Prepare for Qdrant
            qdrant_chunks = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = QdrantManager.generate_chunk_id(
                    ticker=ticker,
                    source='wikipedia',
                    content=chunk,
                    index=i
                )
                
                # Calculate token count
                chunk_tokens = len(self.chunker.encoding.encode(chunk)) if hasattr(self.chunker, 'encoding') else len(chunk) // 4
                
                # Enhanced metadata structure (matching test_apple_2024.py)
                metadata = {
                    # ===== Core Identifiers =====
                    'ticker': ticker,
                    'company_name': company.name,
                    'source': 'wikipedia',  # Was 'data_source_type'
                    
                    # ===== Page Metadata =====
                    'page_title': page_data['page_title'],
                    'page_url': page_data.get('page_url', ''),
                    'revision_id': current_revision,
                    'last_modified': last_modified,  # NEW
                    
                    # ===== Chunk Metadata =====
                    'chunk_index': i,
                    'total_chunks': total_chunks,  # NEW
                    'chunk_size': len(chunk),  # Was 'chunk_length'
                    'chunk_tokens': chunk_tokens,  # NEW
                    'chunk_text': chunk,  # For compatibility
                    
                    # ===== Section Metadata =====  
                    'section': 'Introduction',  # TODO: Track during parsing
                    
                    # ===== Table Metadata =====
                    'has_tables': False,  # NEW (Wikipedia doesn't have tables in this impl)
                    'table_references': [],  # NEW
                    
                    # ===== Storage =====
                    'gcs_path': gcs_path,  # NEW
                    
                    # ===== Timestamps =====
                    'processed_date': current_time,  # NEW
                    'fetched_date': current_time,
                    'created_at': current_time,  # NEW
                    'last_revision_check': current_time,  # NEW
                    'expires_at': None,  # Wikipedia doesn't expire
                    
                    # ===== Bias Mitigation =====
                    'boost_factor': 0.12,  # NEW (default for medium companies)
                    'coverage_classification': 'medium'  # NEW
                }
                
                qdrant_chunks.append({
                    'chunk_id': chunk_id,
                    'vector': embedding,
                    'raw_chunk': chunk,
                    'metadata': metadata
                })
            
            # Delete old chunks if this is an update
            if existing_page:
                logger.info(f"Deleting old Wikipedia chunks for {ticker}")
                self.qdrant.delete_by_filter({
                    'ticker': ticker,
                    'source': 'wikipedia'  # Was 'data_source_type'
                })
            
            # Store new chunks in Qdrant
            logger.info(f"Storing {len(qdrant_chunks)} Wikipedia chunks in Qdrant")
            self.qdrant.upsert_chunks(qdrant_chunks, batch_size=100)
            
            # Update PostgreSQL
            page_metadata = {
                'ticker': ticker,
                'company_name': company.name,
                'page_title': page_data['page_title'],
                'page_id': page_data.get('revision_id'),
                'revision_id': current_revision,
                'content_hash': content_hash
            }
            
            wiki_id = self.postgres.upsert_wikipedia_page(page_metadata)
            self.postgres.update_wikipedia_status(ticker, 'completed', chunks=len(qdrant_chunks))
            
            result = {
                'status': 'success',
                'ticker': ticker,
                'revision_id': current_revision,
                'total_chunks': len(qdrant_chunks),
                'action': 'updated' if existing_page else 'created'
            }
            
            logger.info(f"✓ Successfully processed Wikipedia for {ticker}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process Wikipedia page: {e}", exc_info=True)
            
            # Update status
            self.postgres.update_wikipedia_status(ticker, 'failed', error=str(e))
            
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def process_all_companies(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Process Wikipedia pages for all configured companies
        
        Args:
            force_refresh: Force re-processing even if not changed
        
        Returns:
            Summary dict
        """
        tickers = config.get_all_tickers()
        
        logger.info(f"Processing Wikipedia for {len(tickers)} companies")
        
        results = {
            'total': len(tickers),
            'processed': 0,
            'skipped': 0,
            'failed': 0,
            'details': []
        }
        
        for ticker in tickers:
            result = self.process_page(ticker, force_refresh=force_refresh)
            
            if result['status'] == 'success':
                results['processed'] += 1
            elif result['status'] == 'skipped':
                results['skipped'] += 1
            else:
                results['failed'] += 1
            
            results['details'].append(result)
        
        logger.info(f"Completed Wikipedia processing: {results['processed']} processed, "
                   f"{results['skipped']} skipped, {results['failed']} failed")
        
        return results
    
    @staticmethod
    def _hash_content(content: str) -> str:
        """Generate SHA256 hash of content"""
        return hashlib.sha256(content.encode()).hexdigest()