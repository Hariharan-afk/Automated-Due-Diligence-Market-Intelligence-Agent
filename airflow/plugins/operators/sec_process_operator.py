# airflow/plugins/operators/sec_process_operator.py
"""
Custom Airflow operator for SEC filing processing

Encapsulates complete workflow:
- Fetch SEC filings
- Parse sections (tables + text)
- Generate embeddings
- Store in databases
"""

from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from typing import List, Optional
from datetime import datetime, timedelta


class SECProcessOperator(BaseOperator):
    """
    Custom operator for SEC filing processing

    Workflow:
    1. Fetch filings for ticker
    2. Check for duplicates in database
    3. Parse sections (split tables/text)
    4. Generate chunks with section-aware sizing
    5. Create embeddings
    6. Store in PostgreSQL + Qdrant + Blob storage

    Args:
        ticker: Company ticker symbol
        filing_types: List of filing types (default: ['10-K', '10-Q'])
        lookback_days: Number of days to look back for new filings (default: 7)
        skip_existing: Whether to skip already-processed filings (default: True)
    """

    template_fields = ['ticker', 'filing_types', 'lookback_days']
    ui_color = '#e8f4f8'

    @apply_defaults
    def __init__(
        self,
        ticker: str,
        filing_types: Optional[List[str]] = None,
        lookback_days: int = 7,
        skip_existing: bool = True,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.ticker = ticker
        self.filing_types = filing_types or ['10-K', '10-Q']
        self.lookback_days = lookback_days
        self.skip_existing = skip_existing

    def execute(self, context):
        """
        Execute SEC filing processing

        Lazy imports to reduce DAG parsing time
        """
        # Lazy imports
        import sys
        from pathlib import Path
        sys.path.insert(0, '/opt/airflow')

        from src.data_ingestion.sec_fetcher import SECFetcher
        from src.data_processing.sec_parser import SECParser
        from src.data_processing.metadata_enricher import MetadataEnricher
        from src.embeddings.embedding_generator import EmbeddingGenerator
        from src.storage.vector_store_manager import VectorStoreManager
        from src.storage.metadata_store_manager import MetadataStoreManager
        from src.storage.blob_storage_manager import BlobStorageManager
        from src.utils.logging_config import get_logger

        logger = get_logger(f"SECProcessOperator.{self.ticker}")
        logger.info(f"Starting SEC processing for {self.ticker}")

        # Initialize components
        fetcher = SECFetcher()
        parser = SECParser()
        enricher = MetadataEnricher()
        embedder = EmbeddingGenerator()
        vector_store = VectorStoreManager()
        metadata_store = MetadataStoreManager()
        blob_storage = BlobStorageManager()

        # Step 1: Fetch filings
        from_date = (datetime.now() - timedelta(days=self.lookback_days)).strftime('%Y-%m-%d')

        self.log.info(f"Fetching {self.filing_types} for {self.ticker} since {from_date}")

        try:
            filings = fetcher.fetch_filings(
                ticker=self.ticker,
                filing_types=self.filing_types,
                from_date=from_date
            )
        except Exception as e:
            self.log.error(f"Failed to fetch filings for {self.ticker}: {e}")
            raise

        if not filings:
            self.log.info(f"No filings found for {self.ticker}")
            return {'filings_processed': 0, 'chunks_created': 0}

        # Step 2: Filter out existing filings
        if self.skip_existing:
            new_filings = []
            for filing in filings:
                if not metadata_store.check_filing_exists(filing['accession_number']):
                    new_filings.append(filing)
            filings = new_filings

        if not filings:
            self.log.info(f"No new filings to process for {self.ticker}")
            return {'filings_processed': 0, 'chunks_created': 0}

        self.log.info(f"Processing {len(filings)} new filings for {self.ticker}")

        # Step 3: Process each filing
        total_chunks = 0
        processed_count = 0

        for filing in filings:
            try:
                self.log.info(
                    f"Processing {self.ticker} {filing['filing_type']} "
                    f"FY{filing.get('fiscal_year', 'N/A')}"
                )

                # Save filing metadata
                filing_id = metadata_store.save_filing_metadata(filing)
                metadata_store.update_filing_status(filing['accession_number'], 'processing')

                all_chunks = []

                # Process each section
                for section_code, section_content in filing.get('sections', {}).items():
                    section_name = filing.get('section_names', {}).get(section_code, section_code)

                    # Create source metadata
                    source_metadata = enricher.create_source_metadata_sec(
                        ticker=self.ticker,
                        filing_type=filing['filing_type'],
                        filing_date=filing['filing_date'],
                        fiscal_year=filing.get('fiscal_year'),
                        accession_number=filing['accession_number'],
                        section=section_code,
                        filing_url=filing.get('filing_url', ''),
                        fiscal_quarter=filing.get('fiscal_quarter')
                    )

                    # Parse section
                    parsed_results = parser.parse_filing_section(
                        section_content=section_content,
                        section_code=section_code,
                        section_name=section_name,
                        filing_metadata=source_metadata
                    )

                    all_chunks.extend(parsed_results['text_chunks'])
                    all_chunks.extend(parsed_results['table_chunks'])

                # Generate embeddings
                self.log.info(f"Generating embeddings for {len(all_chunks)} chunks")
                embedded_chunks = embedder.generate_embeddings(all_chunks)

                # Store in vector database
                vector_store.upsert_chunks(embedded_chunks)

                # Update metadata
                metadata_store.update_filing_processing_complete(
                    accession_number=filing['accession_number'],
                    total_chunks=len(all_chunks),
                    text_chunks=len([c for c in all_chunks if c.get('chunk_type') == 'text']),
                    table_chunks=len([c for c in all_chunks if c.get('chunk_type') == 'table'])
                )
                metadata_store.mark_filing_indexed(filing['accession_number'])

                # Save to blob storage
                blob_storage.save_sec_filing(
                    ticker=self.ticker,
                    filing_type=filing['filing_type'],
                    filing_date=filing['filing_date'],
                    data=filing
                )

                total_chunks += len(all_chunks)
                processed_count += 1

                self.log.info(
                    f"✅ Processed {filing['filing_type']} FY{filing.get('fiscal_year')}: "
                    f"{len(all_chunks)} chunks"
                )

            except Exception as e:
                self.log.error(f"Error processing filing {filing['accession_number']}: {e}")
                metadata_store.update_filing_status(filing['accession_number'], 'failed')
                continue

        # Return summary
        summary = {
            'ticker': self.ticker,
            'filings_processed': processed_count,
            'chunks_created': total_chunks
        }

        self.log.info(
            f"✅ SEC processing complete for {self.ticker}: "
            f"{processed_count} filings, {total_chunks} chunks"
        )

        return summary
