"""
Initial Load DAG - One-time Load Historical historical Data

Fetches and processes data for all companies:
- SEC Filings (10-K, 10-Q) from 2023+
- Wikipedia pages
- News articles (last 30 days)

Schedule: Manual trigger only
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.utils.task_group import TaskGroup

# Default arguments
default_args = {
    'owner': 'data_pipeline',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# DAG definition
dag = DAG(
    'initial_load',
    default_args=default_args,
    description='Initial historical data load for all companies',
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2024, 12, 1),
    catchup=False,
    tags=['initial', 'historical', 'all-companies'],
)


def load_companies(**context):
    """Load companies list from configuration"""
    import sys
    from pathlib import Path
    
    # Add project root to path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))    
    
    from src.orchestration.utils.airflow_helpers import get_companies_list
    
    companies = get_companies_list()
    context['task_instance'].xcom_push(key='companies', value=companies)
    
    return f"Loaded {len(companies)} companies"


def process_company_data(ticker, company_name, cik, **context):
    """
    Process all data for a single company
    
    This is the main processing function that:
    1. Fetches SEC filings, Wikipedia, News
    2. Processes and chunks text
    3. Generates embeddings
    4. Uploads to cloud (GCS + Qdrant)
    """
    import sys
    from pathlib import Path
    import os
    from dotenv import load_dotenv
    
    # Setup paths
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    load_dotenv()
    
    # Import processing components
    from src.data_ingestion.sec_fetcher import SECFetcher
    from src.data_ingestion.wikipedia_fetcher import WikipediaFetcher
    from src.data_ingestion.news_fetcher import NewsFetcher
    from src.data_processing.chunker import TextChunker
    from src.data_processing.table_processor import TableProcessor
    from src.utils.table_summarizer import GroqTableSummarizer
    from src.embedding import Embedder
    from src.cloud import GCSConnector, QdrantConnector
    
    print(f"\n{'='*80}")
    print(f"PROCESSING: {company_name} ({ticker})")
    print(f"{'='*80}\n")
    
    # Initialize components
    print("🔧 Initializing components...")
    
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
    
    # Ensure collection exists
    try:
        qdrant.create_collection(
            collection_name=collection_name,
            vector_size=1024,
            distance='Cosine',
            recreate=False
        )
    except:
        pass  # Collection already exists
    
    stats = {
        'sec': {'filings': 0, 'chunks': 0, 'tables': 0},
        'wikipedia': {'pages': 0, 'chunks': 0},
        'news': {'articles': 0, 'chunks': 0}
    }
    
    # === 1. Process SEC Filings ===
    print("\n📄 Processing SEC Filings...")
    try:
        sec_fetcher = SECFetcher(user_identity=os.getenv('SEC_API_KEY', 'your.email@example.com'))
        
        # Fetch 2023+ filings
        filings = sec_fetcher.fetch_filings_by_cik(
            cik=cik,
            filing_types=['10-K', '10-Q'],
            start_date='2023-01-01',
            end_date=datetime.now().strftime('%Y-%m-%d')
        )
        
        stats['sec']['filings'] = len(filings)
        print(f"   Found {len(filings)} filings")
        
        # Process each filing
        for filing in filings:
            print(f"   Processing {filing['filing_type']} - {filing['filing_date']}")
            
            for section in filing['sections']:
                # Process tables
                processed_text, tables = table_processor.process_section(
                    section_html=section.get('section_html_doc'),
                    section_text=section['section_text'],
                    metadata={'ticker': ticker, 'filing_type': filing['filing_type']}
                )
                
                stats['sec']['tables'] += len(tables)
                
                # Chunk text
                chunks = chunker.chunk_text(processed_text)
                if not chunks:
                    continue
                
                stats['sec']['chunks'] += len(chunks)
                
                # Generate embeddings
                embeddings = embedder.embed_documents(chunks, batch_size=32)
                
                # Upload raw data to GCS
                gcs_path = f"raw/sec/{ticker}/{filing['fiscal_year']}/{filing['accession_number']}_section_{section['section_code']}.json"
                gcs.upload_data(
                    data={
                        'filing_metadata': {
                            'ticker': ticker,
                            'filing_type': filing['filing_type'],
                            'accession_number': filing['accession_number']
                        },
                        'section': {'code': section['section_code'], 'name': section['section_name']},
                        'tables': tables,
                        'chunks': chunks
                    },
                    gcs_path=gcs_path
                )
                
                # Upload to Qdrant with metadata
                current_time = datetime.utcnow().isoformat() + 'Z'
                payloads = []
                for i, chunk_text in enumerate(chunks):
                    chunk_tokens = len(chunker.encoding.encode(chunk_text))
                    payloads.append({
                        'chunk_id': f"{ticker}_sec_{filing['accession_number']}_{section['section_code']}_{i}",
                        'ticker': ticker,
                        'company': company_name,
                        'data_source': 'sec',
                        'filing_type': filing['filing_type'],
                        'section': section['section_code'],
                        'chunk_text': chunk_text,
                        'chunk_tokens': chunk_tokens,
                        'created_at': current_time
                    })
                
                qdrant.upload_vectors(collection_name=collection_name, vectors=embeddings, payloads=payloads)
    
    except Exception as e:
        print(f"   ❌ SEC Error: {e}")
    
    # === 2. Process Wikipedia ===
    print("\n📖 Processing Wikipedia...")
    try:
        wiki_fetcher = WikipediaFetcher()
        page = wiki_fetcher.fetch(company_name)
        
        stats['wikipedia']['pages'] = 1
        
        # Chunk content
        chunks = chunker.chunk_text(page['text_content'])
        stats['wikipedia']['chunks'] = len(chunks)
        
        # Generate embeddings
        embeddings = embedder.embed_documents(chunks, batch_size=32)
        
        # Upload to GCS
        gcs_path = f"raw/wikipedia/{ticker}/{page['page_title'].replace(' ', '_')}.json"
        gcs.upload_data(
            data={'page_metadata': {'title': page['page_title']}, 'content': page['text_content'], 'chunks': chunks},
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
                'chunk_text': chunk_text,
                'chunk_tokens': chunk_tokens,
                'created_at': current_time
            })
        
        qdrant.upload_vectors(collection_name=collection_name, vectors=embeddings, payloads=payloads)
        
    except Exception as e:
        print(f"   ❌ Wikipedia Error: {e}")
    
    # === 3. Process News ===
    print("\n📰 Processing News...")
    try:
        news_fetcher = NewsFetcher(mode='auto')
        articles = news_fetcher.fetch_by_ticker(ticker=ticker, days_back=30, max_records=20)
        
        stats['news']['articles'] = len(articles)
        
        for article in articles:
            chunks = chunker.chunk_text(article['content'])
            if not chunks:
                continue
            
            stats['news']['chunks'] += len(chunks)
            
            # Generate embeddings
            embeddings = embedder.embed_documents(chunks, batch_size=32)
            
            # Upload to GCS
            pub_date = datetime.now()  # Simplified
            gcs_path = f"raw/news/{ticker}/{pub_date.strftime('%Y%m%d')}_{article['url'].split('/')[-1][:50]}.json"
            gcs.upload_data(
                data={'article_metadata': {'title': article['title']}, 'content': article['content'], 'chunks': chunks},
                gcs_path=gcs_path
            )
            
            # Upload to Qdrant
            current_time = datetime.utcnow().isoformat() + 'Z'
            payloads = []
            for i, chunk_text in enumerate(chunks):
                chunk_tokens = len(chunker.encoding.encode(chunk_text))
                payloads.append({
                    'chunk_id': f"{ticker}_news_{i}",
                    'ticker': ticker,
                    'company': company_name,
                    'data_source': 'news',
                    'article_title': article['title'],
                    'chunk_text': chunk_text,
                    'chunk_tokens': chunk_tokens,
                    'created_at': current_time
                })
            
            qdrant.upload_vectors(collection_name=collection_name, vectors=embeddings, payloads=payloads)
    
    except Exception as e:
        print(f"   ❌ News Error: {e}")
    
    # Summary
    print(f"\n✅ COMPLETED: {ticker}")
    print(f"   SEC: {stats['sec']['filings']} filings, {stats['sec']['chunks']} chunks")
    print(f"   Wikipedia: {stats['wikipedia']['pages']} page, {stats['wikipedia']['chunks']} chunks")
    print(f"   News: {stats['news']['articles']} articles, {stats['news']['chunks']} chunks")
    
    return stats


# === DAG Tasks ===

start = DummyOperator(task_id='start', dag=dag)

load_companies_task = PythonOperator(
    task_id='load_companies',
    python_callable=load_companies,
    provide_context=True,
    dag=dag,
)

# For now, create a simple task that processes AAPL as an example
# In production, you'd use dynamic task mapping for all companies

process_aapl = PythonOperator(
    task_id='process_AAPL',
    python_callable=process_company_data,
    op_kwargs={
        'ticker': 'AAPL',
        'company_name': 'Apple Inc.',
        'cik': '0000320193'
    },
    provide_context=True,
    execution_timeout=timedelta(hours=2),
    dag=dag,
)

end = DummyOperator(task_id='end', dag=dag)

# Task dependencies
start >> load_companies_task >> process_aapl >> end
