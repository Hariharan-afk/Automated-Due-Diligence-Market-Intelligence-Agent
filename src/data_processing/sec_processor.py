# src/data_processing/sec_processor.py
"""SEC filing processor - orchestrates the complete SEC workflow"""

from typing import Dict, List, Any, Optional
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data_ingestion.sec_fetcher import SECFetcher
from src.data_processing.sec_parser import SECParser
from src.data_processing.chunker import TextChunker
from src.data_processing.table_detector import FinancialTableDetector
from src.data_processing.embedder import FinancialEmbedder
from src.storage.postgres_manager import PostgresManager
from src.storage.qdrant_manager import QdrantManager
from src.utils.llm_client import LLMClient
from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SECProcessor:
    """
    Orchestrates the complete SEC filing processing workflow
    
    Workflow:
    1. Fetch filing from SEC
    2. Extract configured sections
    3. Convert HTML → Markdown (MarkItDown)
    4. Split by horizontal lines (---)
    5. Detect financial tables
    6. Generate LLM headers for high-confidence tables
    7. Chunk text (with overlap)
    8. Embed chunks (FinE5)
    9. Store in Qdrant + PostgreSQL
    """
    
    def __init__(
        self,
        postgres_manager: PostgresManager,
        qdrant_manager: QdrantManager,
        embedder: FinancialEmbedder,
        llm_client: LLMClient
    ):
        """
        Initialize SEC processor
        
        Args:
            postgres_manager: PostgreSQL manager instance
            qdrant_manager: Qdrant manager instance
            embedder: Embedder instance
            llm_client: LLM client instance
        """
        self.postgres = postgres_manager
        self.qdrant = qdrant_manager
        self.embedder = embedder
        self.llm_client = llm_client
        
        # Initialize components
        self.fetcher = SECFetcher()
        self.parser = SECParser()
        self.chunker = TextChunker(chunk_size=800, overlap=100)
        self.table_detector = FinancialTableDetector(
            confidence_threshold=config.llm_config.get('table_confidence_threshold', 0.6)
        )
        
        logger.info("SECProcessor initialized")
    
    def process_filing(
        self,
        ticker: str,
        filing_type: str,
        accession_number: str,
        filing_date: str,
        fiscal_year: int,
        fiscal_quarter: Optional[int] = None,
        filing_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a single SEC filing
        
        Args:
            ticker: Company ticker
            filing_type: '10-K' or '10-Q'
            accession_number: Filing accession number
            filing_date: Filing date (YYYY-MM-DD)
            fiscal_year: Fiscal year
            fiscal_quarter: Fiscal quarter (None for 10-K)
            filing_url: Direct URL to filing (optional)
        
        Returns:
            Processing result dict
        """
        logger.info(f"Processing {ticker} {filing_type} FY{fiscal_year} "
                   f"{'Q' + str(fiscal_quarter) if fiscal_quarter else ''}")
        
        # Get company info
        company = config.get_company_by_ticker(ticker)
        if not company:
            raise ValueError(f"Company {ticker} not found")
        
        # Create filing metadata for PostgreSQL
        filing_data = {
            'ticker': ticker,
            'cik': company.cik,
            'company_name': company.name,
            'filing_type': filing_type,
            'fiscal_year': fiscal_year,
            'fiscal_quarter': fiscal_quarter,
            'accession_number': accession_number,
            'filing_date': filing_date,
            'filing_url': filing_url  # Add filing URL
        }
        
        # Insert/update filing in PostgreSQL
        filing_id = self.postgres.insert_sec_filing(filing_data)
        self.postgres.update_sec_filing_status(filing_id, 'processing')
        
        try:
            # Get sections to fetch
            sections_config = config.get_sec_sections(filing_type)
            
            logger.info(f"Fetching {len(sections_config)} sections...")
            
            # Fetch sections from SEC
            sections_html = self.fetcher.fetch_filing_sections(
                # accession_number=accession_number,
                sections=sections_config,
                filing_type=filing_type,
                filing_url=filing_data.get('filing_url')  # Pass filing URL if available
            )
            
            # Update sections_fetched in DB
            sections_fetched = {code: True for code in sections_html.keys()}
            self.postgres.update_sec_filing_sections(filing_id, sections_fetched)
            
            # Parse sections to markdown
            logger.info("Parsing sections to markdown...")
            parsed_sections = self.parser.parse_multiple_sections(
                sections_html=sections_html,
                section_names=sections_config,
                filing_metadata=filing_data
            )
            
            # Process all chunks from all sections
            all_chunks_data = []
            
            for section in parsed_sections:
                logger.info(f"Processing section {section['section_code']}: {section['section_name']}")
                
                # Process each chunk from the section
                chunks_data = self._process_section_chunks(
                    chunks=section['chunks'],
                    section_code=section['section_code'],
                    section_name=section['section_name'],
                    filing_metadata=filing_data
                )
                
                all_chunks_data.extend(chunks_data)
            
            logger.info(f"Total chunks to embed and store: {len(all_chunks_data)}")
            
            # Embed all chunks
            logger.info("Embedding chunks...")
            chunk_texts = [c['chunk_text'] for c in all_chunks_data]
            embeddings = self.embedder.embed_chunks(chunk_texts, show_progress=True)
            
            # Add embeddings to chunks
            for i, chunk_data in enumerate(all_chunks_data):
                chunk_data['vector'] = embeddings[i]
            
            # Prepare for Qdrant storage
            qdrant_chunks = []
            for i, chunk_data in enumerate(all_chunks_data):
                chunk_id = QdrantManager.generate_chunk_id(
                    ticker=ticker,
                    source='sec',
                    content=chunk_data['chunk_text'],
                    index=i
                )
                
                qdrant_chunks.append({
                    'chunk_id': chunk_id,
                    'vector': chunk_data['vector'],
                    'raw_chunk': chunk_data['chunk_text'],
                    'metadata': chunk_data['metadata']
                })
            
            # Store in Qdrant
            logger.info(f"Storing {len(qdrant_chunks)} chunks in Qdrant...")
            self.qdrant.upsert_chunks(qdrant_chunks, batch_size=100)
            
            # Update filing status in PostgreSQL
            self.postgres.update_sec_filing_status(
                filing_id=filing_id,
                status='completed',
                chunks=len(qdrant_chunks)
            )
            
            result = {
                'status': 'success',
                'filing_id': filing_id,
                'sections_processed': len(parsed_sections),
                'total_chunks': len(qdrant_chunks),
                'financial_table_chunks': sum(
                    1 for c in all_chunks_data 
                    if c['metadata'].get('contains_financial_table', False)
                )
            }
            
            logger.info(f"✓ Successfully processed {ticker} {filing_type} FY{fiscal_year}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process filing: {e}", exc_info=True)
            
            # Update status to failed
            self.postgres.update_sec_filing_status(
                filing_id=filing_id,
                status='failed',
                error=str(e)
            )
            
            return {
                'status': 'failed',
                'error': str(e),
                'filing_id': filing_id
            }
    
    def _process_section_chunks(
        self,
        chunks: List[str],
        section_code: str,
        section_name: str,
        filing_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Process chunks from a section with comprehensive metadata
        
        Steps:
        1. Detect financial tables
        2. Generate LLM headers for high-confidence tables
        3. Sub-chunk large chunks if needed
        4. Add comprehensive metadata (matching test_apple_2024.py structure)
        
        Args:
            chunks: List of text chunks (split by ---)
            section_code: Section code (e.g., 'Item7')
            section_name: Section name (e.g., 'MD&A')
            filing_metadata: Filing metadata dict
        
        Returns:
            List of processed chunk dicts with comprehensive metadata
        """
        processed_chunks = []
        ticker = filing_metadata['ticker']
        accession = filing_metadata['accession_number']
        
        # Calculate total chunks first (needed for metadata)
        temp_chunks_count = 0
        for chunk in chunks:
            table_analysis = self.table_detector.analyze_chunk(chunk)
            is_financial_table = table_analysis['is_financial_table']
            preserve_tables = is_financial_table
            sub_chunks = self.chunker.chunk_text(chunk, preserve_tables=preserve_tables)
            temp_chunks_count += len(sub_chunks)
        
        total_chunks = temp_chunks_count
        chunk_counter = 0
        
        # Construct GCS path
        gcs_path = f"raw/sec/{ticker}/{filing_metadata['fiscal_year']}/{accession}_section_{section_code}.json"
        
        # Process chunks (second pass)
        for i, chunk in enumerate(chunks):
            # Detect if chunk contains financial table
            table_analysis = self.table_detector.analyze_chunk(chunk)
            
            is_financial_table = table_analysis['is_financial_table']
            table_confidence = table_analysis['confidence']
            
            # Generate LLM header for high-confidence tables
            llm_header = None
            if is_financial_table and table_confidence >= self.table_detector.confidence_threshold:
                logger.info(f"Generating LLM header for financial table (confidence: {table_confidence:.2f})")
                
                llm_header = self.llm_client.generate_table_header(
                    table_chunk=chunk,
                    company_name=filing_metadata['company_name'],
                    filing_type=filing_metadata['filing_type'],
                    section_name=section_name,
                    fiscal_year=filing_metadata['fiscal_year'],
                    fiscal_quarter=filing_metadata.get('fiscal_quarter')
                )
                
                if llm_header:
                    # Prepend header to chunk
                    chunk = f"**Table Description:** {llm_header}\\n\\n{chunk}"
            
            # Sub-chunk if needed (but preserve tables as single chunks)
            preserve_tables = is_financial_table
            sub_chunks = self.chunker.chunk_text(chunk, preserve_tables=preserve_tables)
            
            # Add metadata to each sub-chunk
            current_time = datetime.utcnow().isoformat() + 'Z'
            
            for j, sub_chunk in enumerate(sub_chunks):
                # Calculate token count
                chunk_tokens = len(self.chunker.encoding.encode(sub_chunk)) if hasattr(self.chunker, 'encoding') else len(sub_chunk) // 4
                
                # Extract table references from chunk
                # (This requires TableProcessor - simplified for now)
                table_references = []
                if is_financial_table:
                    # Generate table reference for this chunk
                    table_ref = f"TABLE_{ticker}_{accession}_{section_code}_{i}"
                    table_references = [table_ref]
                
                # Enhanced metadata structure (matching test_apple_2024.py)
                metadata = {
                    # ===== Core Identifiers =====
                    'ticker': ticker,
                    'company_name': filing_metadata['company_name'],  # Was 'company'
                    'source': 'sec',  # Was 'data_source_type'
                    
                    # ===== Filing Metadata =====
                    'filing_type': filing_metadata['filing_type'],
                    'filing_date': filing_metadata['filing_date'],  # NEW
                    'fiscal_year': filing_metadata['fiscal_year'],
                    'fiscal_quarter': filing_metadata.get('fiscal_quarter'),  # Was 'quarter'
                    'accession_number': accession,  # NEW
                    'filing_url': filing_metadata.get('filing_url', ''),  # NEW
                    
                    # ===== Section Metadata =====
                    'section_code': section_code,  # Was 'section_item'
                    'section_title': section_name,  # Was 'section_item_name'
                    
                    # ===== Chunk Metadata =====
                    'chunk_index': chunk_counter,  # Global index
                    'total_chunks': total_chunks,  # NEW
                    'chunk_size': len(sub_chunk),  # Was 'chunk_length'
                    'chunk_tokens': chunk_tokens,  # Keep for compatibility
                    
                    # ===== Table Metadata =====
                    'has_tables': is_financial_table,  # Was 'contains_financial_table'
                    'table_references': table_references,  # NEW
                    'table_confidence': table_confidence if is_financial_table else 0.0,
                    'has_llm_header': llm_header is not None,
                    
                    # ===== Storage =====
                    'gcs_path': gcs_path,  # NEW
                    
                    # ===== Timestamps =====
                    'processed_date': current_time,  # NEW
                    'fetched_date': current_time,  # Keep for backward compatibility
                    'created_at': current_time,  # NEW
                    'expires_at': None,  # SEC filings don't expire
                    
                    # ===== Bias Mitigation =====
                    # NOTE: boost_factor calculation requires BaselineCalculator
                    # For now, use default value. Will be enhanced in next iteration.
                    'boost_factor': 0.0,  # Default for large companies
                    'coverage_classification': 'medium'  # Will be calculated dynamically
                }
                
                # Store cik for completeness
                if 'cik' in filing_metadata:
                    metadata['cik'] = filing_metadata['cik']
                
                processed_chunks.append({
                    'chunk_text': sub_chunk,
                    'metadata': metadata
                })
                
                chunk_counter += 1
        
        logger.info(f"Processed {len(chunks)} initial chunks → {len(processed_chunks)} final chunks")
        
        return processed_chunks
    
    def process_company_filings(
        self,
        ticker: str,
        filing_types: List[str] = None,
        start_date: str = "2023-01-01",
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Process all filings for a company
        
        Args:
            ticker: Company ticker
            filing_types: List of filing types (default: ['10-K', '10-Q'])
            start_date: Start date for fetching
            skip_existing: Skip filings already in DB
        
        Returns:
            Summary dict
        """
        if filing_types is None:
            filing_types = ['10-K', '10-Q']
        
        logger.info(f"Processing {ticker} filings from {start_date}")
        
        # Query available filings from SEC
        filings = self.fetcher.fetch_by_ticker(
            ticker=ticker,
            filing_types=filing_types,
            start_date=start_date
        )
        
        logger.info(f"Found {len(filings)} filings for {ticker}")
        
        if skip_existing:
            # Check which filings are already processed
            existing = self.postgres.get_missing_sec_filings(
                ticker=ticker,
                filing_type=filing_types[0] if len(filing_types) == 1 else None,
                start_year=int(start_date[:4])
            )
            
            existing_accessions = {f['accession_number'] for f in existing}
            filings = [f for f in filings if f['accession_number'] not in existing_accessions]
            
            logger.info(f"After filtering existing: {len(filings)} filings to process")
        
        # Process each filing
        results = {
            'ticker': ticker,
            'total_filings': len(filings),
            'processed': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }
        
        for filing in filings:
            try:
                result = self.process_filing(
                    ticker=ticker,
                    filing_type=filing['filing_type'],
                    accession_number=filing['accession_number'],
                    filing_date=filing['filing_date'],
                    fiscal_year=filing['fiscal_year'],
                    fiscal_quarter=filing.get('fiscal_quarter'),
                    filing_url=filing.get('filing_url')  # Pass filing URL
                )
                
                if result['status'] == 'success':
                    results['processed'] += 1
                else:
                    results['failed'] += 1
                
                results['details'].append(result)
                
            except Exception as e:
                logger.error(f"Failed to process filing {filing['accession_number']}: {e}")
                results['failed'] += 1
        
        logger.info(f"Completed {ticker}: {results['processed']} processed, "
                   f"{results['failed']} failed")
        
        return results