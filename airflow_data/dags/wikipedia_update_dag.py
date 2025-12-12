"""
Wikipedia Update DAG - Weekly Check for Page Changes

Checks Wikipedia pages for updates and refreshes changed content

Schedule: Every Sunday at 2 AM
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
    'wikipedia_update',
    default_args=default_args,
    description='Weekly Wikipedia page update check',
    schedule_interval='0 2 * * 0',  # 2 AM every Sunday
    start_date=datetime(2024, 12, 10),
    catchup=False,
    tags=['wikipedia', 'monitoring', 'weekly'],
)


def check_page_changes(**context):
    """Check if Wikipedia pages have changed"""
    import sys
    from pathlib import Path
    import os
    from dotenv import load_dotenv
    
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    load_dotenv()
    
    from src.data_ingestion.wikipedia_fetcher import WikipediaFetcher
    from src.orchestration.utils.airflow_helpers import get_companies_list
    
    companies = get_companies_list()
    wiki_fetcher = WikipediaFetcher()
    
    changed_pages = []
    
    for company in companies:
        try:
            # Fetch current page
            page = wiki_fetcher.fetch(company['name'])
            
            # For now, we'll process all pages since we don't have stored revision IDs
            # In production, you'd check against PostgreSQL
            changed_pages.append({
                'ticker': company['ticker'],
                'company_name': company['name'],
                'page': page
            })
            
        except Exception as e:
            print(f"Error checking {company['name']}: {e}")
    
    print(f"Found {len(changed_pages)} page(s) to update")
    
    # Push to XCom
    context['task_instance'].xcom_push(key='changed_pages', value=changed_pages)
    
    # Branch decision
    return 'update_pages' if changed_pages else 'skip_update'


def update_wikipedia_pages(**context):
    """Update changed Wikipedia pages"""
    import sys
    from pathlib import Path
    import os
    from dotenv import load_dotenv
    
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    load_dotenv()
    
    from src.data_processing.chunker import TextChunker
    from src.embedding import Embedder
    from src.cloud import GCSConnector, QdrantConnector
    
    # Get changed pages
    changed_pages = context['task_instance'].xcom_pull(key='changed_pages', task_ids='check_page_changes')
    
    if not changed_pages:
        print("No pages to update")
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
    collection_name = os.getenv('QDRANT_COLLECTION', 'company_data')
    
    for item in changed_pages:
        ticker = item['ticker']
        company_name = item['company_name']
        page = item['page']
        
        print(f"\n{'='*60}")
        print(f"Updating: {company_name} ({ticker})")
        print(f"{'='*60}")
        
        # Step 1: Delete old chunks from Qdrant
        try:
            # In production, you'd use filters to delete old chunks
            # For now, we'll just add new chunks (Qdrant will handle duplicates)
            print(f"   Note: In production, old chunks would be deleted here")
        except Exception as e:
            print(f"   Warning: Could not delete old chunks: {e}")
        
        # Step 2: Process new content
        chunks = chunker.chunk_text(page['text_content'])
        
        if not chunks:
            print(f"   No content to process")
            continue
        
        print(f"   Processing {len(chunks)} chunks")
        
        # Generate embeddings
        embeddings = embedder.embed_documents(chunks, batch_size=32)
        
        # Upload to GCS
        gcs_path = f"raw/wikipedia/{ticker}/{page['page_title'].replace(' ', '_')}.json"
        gcs.upload_data(
            data={
                'page_metadata': {
                    'title': page['page_title'],
                    'revision_id': page.get('revision_id'),
                    'updated_at': datetime.utcnow().isoformat()
                },
                'content': page['text_content'],
                'chunks': chunks
            },
            gcs_path=gcs_path
        )
        
        # Upload to Qdrant
        current_time = datetime.utcnow().isoformat() + 'Z'
        payloads = []
        for i, chunk_text in enumerate(chunks):
            chunk_tokens = len(chunker.encoding.encode(chunk_text))
            payloads.append({
                'chunk_id': f"{ticker}_wiki_{i}",
                'ticker': ticker,
                'company': company_name,
                'data_source': 'wikipedia',
                'page_title': page['page_title'],
                'revision_id': page.get('revision_id'),
                'chunk_text': chunk_text,
                'chunk_tokens': chunk_tokens,
                'created_at': current_time
            })
        
        qdrant.upload_vectors(collection_name=collection_name, vectors=embeddings, payloads=payloads)
        
        print(f"   ✓ Uploaded {len(chunks)} chunks")
    
    print(f"\n✅ Updated {len(changed_pages)} Wikipedia page(s)")


# DAG Tasks
start = DummyOperator(task_id='start', dag=dag)

check_task = BranchPythonOperator(
    task_id='check_page_changes',
    python_callable=check_page_changes,
    provide_context=True,
    dag=dag,
)

update_task = PythonOperator(
    task_id='update_pages',
    python_callable=update_wikipedia_pages,
    provide_context=True,
    execution_timeout=timedelta(hours=1),
    dag=dag,
)

skip_task = DummyOperator(task_id='skip_update', dag=dag)

end = DummyOperator(task_id='end', trigger_rule='none_failed_min_one_success', dag=dag)

# Dependencies
start >> check_task >> [update_task, skip_task] >> end
