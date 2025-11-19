# airflow/dags/sec_filings_pipeline.py
"""
SEC Filings Ingestion Pipeline

Schedule: Daily at midnight
- Monitors for new 10-K and 10-Q filings
- Fetches new filings for all tracked companies
- Processes sections (parse, chunk, embed)
- Stores in PostgreSQL + Qdrant
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

# Lazy imports in task functions to reduce DAG parsing time
# Components imported when tasks actually run

# Companies to track
COMPANIES = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']

# Default DAG arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# Create DAG
dag = DAG(
    'sec_filings_pipeline',
    default_args=default_args,
    description='Daily SEC filings ingestion and processing',
    schedule_interval='0 0 * * *',  # Daily at midnight
    start_date=days_ago(1),
    catchup=False,
    tags=['sec', 'filings', 'data-ingestion'],
)


def check_new_filings(**context):
    """
    Check for new SEC filings for all companies

    Returns dict of companies with new filings
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, '/opt/airflow')

    from src.data_ingestion.sec_fetcher import SECFetcher
    from src.storage.metadata_store_manager import MetadataStoreManager
    from src.utils.logging_config import get_logger

    logger = get_logger(__name__)

    fetcher = SECFetcher()
    db = MetadataStoreManager()

    new_filings_found = {}

    for ticker in COMPANIES:
        try:
            # Fetch recent filings (last 7 days to ensure we don't miss anything)
            recent_filings = fetcher.query_filings(
                ticker=ticker,
                filing_types=['10-K', '10-Q'],
                start_date=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            )

            # Check which are new or need reprocessing (failed/pending)
            new_filings = []
            for filing in recent_filings:
                accession_no = filing['accessionNo']
                existing_filing = db.get_filing_by_accession(accession_no)
                
                # Only skip if filing exists AND is successfully completed
                if existing_filing and existing_filing.get('status') == 'completed':
                    logger.debug(f"Skipping {accession_no} - already completed")
                    continue
                
                # Include if new, or if failed/pending (needs reprocessing)
                new_filings.append(filing)

            if new_filings:
                new_filings_found[ticker] = new_filings
                logger.info(f"Found {len(new_filings)} new filings for {ticker}")
            else:
                logger.info(f"No new filings for {ticker}")

        except Exception as e:
            logger.error(f"Error checking filings for {ticker}: {e}")
            continue

    # Push to XCom for downstream tasks
    context['task_instance'].xcom_push(key='new_filings', value=new_filings_found)

    logger.info(f"Total new filings: {sum(len(f) for f in new_filings_found.values())}")
    return len(new_filings_found)


def process_company_filings(ticker, **context):
    """
    Process all new filings for a company

    Lazy imports for efficiency
    """
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

    logger = get_logger(__name__)

    # Get new filings from upstream task
    new_filings_dict = context['task_instance'].xcom_pull(
        task_ids='check_new_filings',
        key='new_filings'
    )

    if not new_filings_dict or ticker not in new_filings_dict:
        logger.info(f"No new filings to process for {ticker}")
        return

    filings_metadata = new_filings_dict[ticker]
    logger.info(f"Processing {len(filings_metadata)} filings for {ticker}")

    # Initialize components
    fetcher = SECFetcher()
    parser = SECParser()
    enricher = MetadataEnricher()
    embedder = EmbeddingGenerator()
    vector_store = VectorStoreManager()
    metadata_store = MetadataStoreManager()
    blob_storage = BlobStorageManager()

    # Fetch sections for each filing
    for filing_metadata in filings_metadata:
        accession_no = filing_metadata['accessionNo']
        filing_type = filing_metadata['formType']
        filing_url = filing_metadata['linkToFilingDetails']
        
        logger.info(f"Fetching sections for {ticker} {filing_type} {accession_no}")
        
        # Get section codes for this filing type
        section_codes = fetcher.get_section_codes(filing_type)
        
        # Extract sections
        extracted_sections = {}
        section_names = {}
        for section_code, section_name in section_codes.items():
            section_text = fetcher.extract_section(
                filing_url=filing_url,
                section_code=section_code,
                filing_accession=accession_no
            )
            if section_text:
                extracted_sections[section_code] = section_text
                section_names[section_code] = section_name
        
        if not extracted_sections:
            logger.warning(f"No sections extracted for {accession_no}, skipping")
            continue
        
        # Build complete filing dict with sections
        filing = {
            **filing_metadata,
            'sections': extracted_sections,
            'section_names': section_names
        }
        try:
            logger.info(
                f"Processing {ticker} {filing['formType']} "
                f"for FY{filing.get('fiscalYear', 'N/A')}"
            )

            # Save filing metadata
            filing_id = metadata_store.save_filing_metadata(
                ticker=ticker,
                filing_type=filing['formType'],
                filing_date=filing['filedAt'].split('T')[0] if 'T' in filing['filedAt'] else filing['filedAt'],
                accession_number=filing['accessionNo'],
                filing_url=filing.get('linkToFilingDetails', ''),
                fiscal_year=filing.get('fiscalYear'),
                fiscal_quarter=filing.get('fiscalQuarter')
            )
            metadata_store.update_filing_status(filing_id, 'processing')

            all_chunks = []

            # Process each section
            for section_code, section_content in filing.get('sections', {}).items():
                section_name = filing.get('section_names', {}).get(section_code, section_code)

                # Create source metadata for chunks
                source_metadata = enricher.create_source_metadata_sec(
                    ticker=ticker,
                    filing_type=filing['formType'],
                    filing_date=filing['filedAt'],
                    fiscal_year=filing.get('fiscalYear'),
                    accession_number=filing['accessionNo'],
                    section=section_code,
                    filing_url=filing.get('linkToFilingDetails', ''),
                    fiscal_quarter=filing.get('fiscalQuarter')
                )

                # Parse section (tables + text)
                parsed_results = parser.parse_filing_section(
                    section_content=section_content,
                    section_code=section_code,
                    section_name=section_name,
                    filing_metadata=source_metadata
                )
                logger.info(f"DEBUG: parsed_results type: {type(parsed_results)}")
                logger.info(f"DEBUG: parsed_results keys: {parsed_results.keys() if isinstance(parsed_results, dict) else 'NOT A DICT'}")
                # Collect all chunks (ensure they're dicts, not lists)
                text_chunks = parsed_results.get('text_chunks', [])
                table_chunks = parsed_results.get('table_chunks', [])
                
                logger.info(f"DEBUG: text_chunks length: {len(text_chunks)}")
                if text_chunks:
                    logger.info(f"DEBUG: First text_chunk type: {type(text_chunks[0])}")
                    logger.info(f"DEBUG: First text_chunk: {str(text_chunks[0])[:300]}")

                logger.info(f"DEBUG: table_chunks length: {len(table_chunks)}")
                if table_chunks:
                    logger.info(f"DEBUG: First table_chunk type: {type(table_chunks[0])}")
                    logger.info(f"DEBUG: First table_chunk: {str(table_chunks[0])[:300]}")

                # Flatten if nested lists somehow
                for chunk in text_chunks:
                    if isinstance(chunk, dict):
                        all_chunks.append(chunk)
                    else:
                        logger.warning(f"Unexpected chunk type in text_chunks: {type(chunk)}")
                
                for chunk in table_chunks:
                    if isinstance(chunk, dict):
                        all_chunks.append(chunk)
                    else:
                        logger.warning(f"Unexpected chunk type in table_chunks: {type(chunk)}")

                logger.info(
                    f"Section {section_code}: {len(text_chunks)} text, "
                    f"{len(table_chunks)} table chunks"
                )

            # Generate embeddings for chunks
            logger.info(f"Generating embeddings for {len(all_chunks)} chunks")
            
            # Prepare chunks for embedding and storage
            prepared_chunks = []
            for i, chunk in enumerate(all_chunks):
                if not isinstance(chunk, dict):
                    logger.warning(f"Skipping invalid chunk at index {i}: {type(chunk)}")
                    continue
                
                # Ensure chunk has required fields
                prepared_chunk = chunk.copy()
                
                # Add chunk_id if missing
                if 'chunk_id' not in prepared_chunk:
                    import uuid
                    prepared_chunk['chunk_id'] = str(uuid.uuid4())
                
                # Ensure text field exists
                if 'text' not in prepared_chunk:
                    logger.warning(f"Chunk {i} missing 'text' field, skipping")
                    continue
                
                # Prepare metadata structure
                if 'metadata' not in prepared_chunk:
                    # Extract metadata from chunk fields
                    metadata_fields = ['ticker', 'filing_type', 'filing_date', 'section_code', 
                                     'section_name', 'chunk_type', 'contains_table', 'source_type']
                    prepared_chunk['metadata'] = {k: prepared_chunk.get(k) for k in metadata_fields if k in prepared_chunk}
                
                prepared_chunks.append(prepared_chunk)
            
            # Generate embeddings using embed_chunks method
            embedded_chunks = embedder.embed_chunks(prepared_chunks)
            # Debug: Check structure
            logger.info(f"Embedded chunks count: {len(embedded_chunks)}")
            if embedded_chunks:
                logger.info(f"First embedded chunk type: {type(embedded_chunks[0])}")
                logger.info(f"First embedded chunk sample: {str(embedded_chunks[0])[:200]}")

            # Store in vector database
            vector_store.upsert_chunks(embedded_chunks)

            # Update metadata
            sections_extracted = list(filing.get('sections', {}).keys())
            
            # Count chunks from embedded_chunks (which are guaranteed to be valid)
            # Count chunks safely (handle both dict and non-dict items)
            text_chunk_count = sum(1 for c in embedded_chunks if isinstance(c, dict) and c.get('chunk_type') == 'text')
            table_chunk_count = sum(1 for c in embedded_chunks if isinstance(c, dict) and c.get('chunk_type') == 'table')
            
            metadata_store.update_filing_processing_complete(
                filing_id=filing_id,
                sections_extracted=sections_extracted,
                total_chunks=len(embedded_chunks),
                text_chunks=text_chunk_count,
                table_chunks=table_chunk_count
            )
            metadata_store.mark_filing_indexed(filing_id)

            # Save raw data to blob storage (combine all sections as content)
            import json
            filing_content = json.dumps(filing, indent=2)
            blob_storage.save_sec_filing(
                ticker=ticker,
                filing_type=filing['formType'],
                filing_date=filing['filedAt'].split('T')[0] if 'T' in filing['filedAt'] else filing['filedAt'],
                accession_number=filing['accessionNo'],
                content=filing_content,
                file_format='json'
            )

            logger.info(
                f"✅ Successfully processed {ticker} {filing['formType']} "
                f"FY{filing.get('fiscalYear', 'N/A')}: {len(all_chunks)} chunks"
            )

        except Exception as e:
            logger.error(f"Error processing filing {accession_no}: {e}")
            # Try to get filing_id if it was saved, otherwise skip status update
            try:
                existing_filing = metadata_store.get_filing_by_accession(accession_no)
                if existing_filing:
                    metadata_store.update_filing_status(existing_filing['id'], 'failed', str(e))
            except Exception as status_error:
                logger.warning(f"Could not update filing status: {status_error}")
            continue


# Task 1: Check for new filings
check_filings_task = PythonOperator(
    task_id='check_new_filings',
    python_callable=check_new_filings,
    dag=dag,
)

# Tasks 2-6: Process each company in parallel
process_tasks = []
for company_ticker in COMPANIES:
    task = PythonOperator(
        task_id=f'process_{company_ticker.lower()}',
        python_callable=process_company_filings,
        op_kwargs={'ticker': company_ticker},
        dag=dag,
    )
    process_tasks.append(task)


def update_pipeline_stats(**context):
    """Update overall pipeline statistics"""
    import sys
    from pathlib import Path
    sys.path.insert(0, '/opt/airflow')

    from src.storage.metadata_store_manager import MetadataStoreManager
    from src.utils.logging_config import get_logger

    logger = get_logger(__name__)

    db = MetadataStoreManager()
    stats = db.get_pipeline_stats()

    logger.info("=== SEC Pipeline Statistics ===")
    logger.info(f"Companies tracked: {stats.get('company_count', 0)}")
    logger.info(f"Total filings: {stats.get('total_filings', 0)}")
    logger.info(f"Total chunks indexed: {stats.get('total_chunks', 0)}")
    logger.info("================================")


# Task 7: Update statistics
stats_task = PythonOperator(
    task_id='update_statistics',
    python_callable=update_pipeline_stats,
    dag=dag,
)

# Define task dependencies
# Check filings → Process all companies in parallel → Update stats
check_filings_task >> process_tasks >> stats_task