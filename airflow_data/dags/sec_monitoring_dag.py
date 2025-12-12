"""
SEC Monitoring DAG - Daily Check for New Filings

Checks for new 10-K/10-Q filings and processes them automatically

Schedule: 6 PM weekdays (after market close)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.dummy import DummyOperator

default_args = {
    'owner': 'data_pipeline',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'sec_monitoring',
    default_args=default_args,
    description='Daily monitoring for new SEC filings',
    schedule_interval='0 18 * * 1-5',  # 6 PM weekdays
    start_date=datetime(2024, 12, 10),
    catchup=False,
    tags=['sec', 'monitoring', 'daily'],
)


def check_new_filings(**context):
    """Check if there are new filings today"""
    import sys
    from pathlib import Path
    import os
    from datetime import datetime
    from dotenv import load_dotenv
    
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    load_dotenv()
    
    from src.data_ingestion.sec_fetcher import SECFetcher
    from src.orchestration.utils.airflow_helpers import get_companies_list
    
    companies = get_companies_list()
    sec_fetcher = SECFetcher(user_identity=os.getenv('SEC_API_KEY', 'your.email@example.com'))
    
    new_filings = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    for company in companies:
        try:
            filings = sec_fetcher.fetch_filings_by_cik(
                cik=company['cik'],
                filing_types=['10-K', '10-Q'],
                start_date=today,
                end_date=today
            )
            
            for filing in filings:
                new_filings.append({
                    'ticker': company['ticker'],
                    'company_name': company['name'],
                    'cik': company['cik'],
                    'filing': filing
                })
        except Exception as e:
            print(f"Error checking {company['ticker']}: {e}")
    
    print(f"Found {len(new_filings)} new filing(s)")
    
    # Push to XCom for processing
    context['task_instance'].xcom_push(key='new_filings', value=new_filings)
    
    # Branch decision
    return 'process_filings' if new_filings else 'skip_processing'


def process_new_filings(**context):
    """Process all new filings"""
    import sys
    from pathlib import Path
    import os
    from dotenv import load_dotenv
    
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    load_dotenv()
    
    from src.data_processing.chunker import TextChunker
    from src.data_processing.table_processor import TableProcessor
    from src.utils.table_summarizer import GroqTableSummarizer
    from src.embedding import Embedder
    from src.cloud import GCSConnector, QdrantConnector
    
    # Get new filings from previous task
    new_filings = context['task_instance'].xcom_pull(key='new_filings', task_ids='check_new_filings')
    
    if not new_filings:
        print("No new filings to process")
        return
    
    # Initialize components
    gcs = GCSConnector(
        bucket_name=os.getenv('GCP_BUCKET_NAME'),
        project_id=os.getenv('GCP_PROJECT_ID'),
        credentials_path=os.getenv('GCP_CREDENTIALS_PATH')
    )
    
    qdrant = QdrantConnector(
        url=os.getenv('QDRANT_URL'),
        api_key=os.getenv('QDRANT_API_KEY')
    )
    
    embedder = Embedder()
    chunker = TextChunker(chunk_size=512, overlap=128)
    table_summarizer = GroqTableSummarizer(api_key=os.getenv('GROQ_API_KEY'))
    table_processor = TableProcessor(summarizer=table_summarizer, min_table_size=0)
    
    collection_name = os.getenv('QDRANT_COLLECTION', 'company_data')
    
    for item in new_filings:
        ticker = item['ticker']
        filing = item['filing']
        
        print(f"\n{'='*60}")
        print(f"Processing: {ticker} - {filing['filing_type']} - {filing['filing_date']}")
        print(f"{'='*60}")
        
        for section in filing['sections']:
            # Process section (similar to initial_load_dag.py)
            processed_text, tables = table_processor.process_section(
                section_html=section.get('section_html_doc'),
                section_text=section['section_text'],
                metadata={'ticker': ticker, 'filing_type': filing['filing_type']}
            )
            
            chunks = chunker.chunk_text(processed_text)
            if not chunks:
                continue
            
            embeddings = embedder.embed_documents(chunks, batch_size=32)
            
            # Upload to GCS
            gcs_path = f"raw/sec/{ticker}/{filing['fiscal_year']}/{filing['accession_number']}_section_{section['section_code']}.json"
            gcs.upload_data(
                data={'filing': filing, 'section': section, 'tables': tables, 'chunks': chunks},
                gcs_path=gcs_path
            )
            
            # Upload to Qdrant
            current_time = datetime.utcnow().isoformat() + 'Z'
            payloads = []
            for i, chunk_text in enumerate(chunks):
                chunk_tokens = len(chunker.encoding.encode(chunk_text))
                payloads.append({
                    'chunk_id': f"{ticker}_sec_{filing['accession_number']}_{section['section_code']}_{i}",
                    'ticker': ticker,
                    'data_source': 'sec',
                    'filing_type': filing['filing_type'],
                    'filing_url': filing.get('url', ''),
                    'accession_number': filing['accession_number'],
                    'filing_date': filing['filing_date'],
                    'fiscal_year': filing['fiscal_year'],
                    'section': section['section_code'],
                    'chunk_text': chunk_text,
                    'chunk_tokens': chunk_tokens,
                    'created_at': current_time
                })
            
            qdrant.upload_vectors(collection_name=collection_name, vectors=embeddings, payloads=payloads)
            
            print(f"   ✓ {section['section_code']}: {len(chunks)} chunks uploaded")
    
    print(f"\n✅ Processed {len(new_filings)} filing(s)")


# DAG Tasks
start = DummyOperator(task_id='start', dag=dag)

check_task = BranchPythonOperator(
    task_id='check_new_filings',
    python_callable=check_new_filings,
    provide_context=True,
    dag=dag,
)

process_task = PythonOperator(
    task_id='process_filings',
    python_callable=process_new_filings,
    provide_context=True,
    execution_timeout=timedelta(hours=2),
    dag=dag,
)

skip_task = DummyOperator(task_id='skip_processing', dag=dag)

end = DummyOperator(task_id='end', trigger_rule='none_failed_min_one_success', dag=dag)

# Dependencies
start >> check_task >> [process_task, skip_task] >> end
