"""
News Fetch DAG - Fetch News Articles Twice Daily

Fetches news for all companies and auto-cleans old articles

Schedule: 9 AM and 5 PM daily
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
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
    'news_fetch',
    default_args=default_args,
    description='Fetch news articles twice daily',
    schedule_interval='0 9,17 * * *',  # 9 AM and 5 PM daily
    start_date=datetime(2024, 12, 10),
    catchup=False,
    tags=['news', 'monitoring', 'daily'],
)


def fetch_news_articles(**context):
    """Fetch news for all companies"""
    import sys
    from pathlib import Path
    import os
    from dotenv import load_dotenv
    
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    load_dotenv()
    
    from src.data_ingestion.news_fetcher import NewsFetcher
    from src.data_processing.chunker import TextChunker
    from src.embedding import Embedder
    from src.cloud import GCSConnector, QdrantConnector
    from src.orchestration.utils.airflow_helpers import get_companies_list
    
    companies = get_companies_list()
    news_fetcher = NewsFetcher(mode='auto')
    
    # Initialize processing components
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
    
    total_articles = 0
    total_chunks = 0
    
    for company in companies:
        ticker = company['ticker']
        company_name = company['name']
        
        print(f"\n{'='*60}")
        print(f"Fetching news for: {company_name} ({ticker})")
        print(f"{'='*60}")
        
        try:
            # Fetch news from last 24 hours
            articles = news_fetcher.fetch_by_ticker(
                ticker=ticker,
                days_back=1,  # Last 24 hours
                max_records=10,
                relevance_threshold=0.3
            )
            
            if not articles:
                print(f"   No new articles found")
                continue
            
            print(f"   Found {len(articles)} article(s)")
            
            for article in articles:
                # Process article
                chunks = chunker.chunk_text(article['content'])
                
                if not chunks:
                    continue
                
                total_chunks += len(chunks)
                
                # Generate embeddings
                embeddings = embedder.embed_documents(chunks, batch_size=32)
                
                # Upload to GCS
                pub_date = datetime.now()
                if article.get('published_at') or article.get('publishedAt'):
                    pub_date_str = article.get('published_at') or article.get('publishedAt')
                    try:
                        pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                    except:
                        pass
                
                gcs_path = f"raw/news/{ticker}/{pub_date.strftime('%Y%m%d')}_{article['url'].split('/')[-1][:50]}.json"
                gcs.upload_data(
                    data={
                        'article_metadata': {
                            'title': article['title'],
                            'url': article['url'],
                            'published_at': pub_date.isoformat(),
                            'relevance_score': article.get('relevance_score', 0)
                        },
                        'content': article['content'],
                        'chunks': chunks
                    },
                    gcs_path=gcs_path
                )
                
                # Upload to Qdrant
                current_time = datetime.utcnow().isoformat() + 'Z'
                expires_at = (pub_date + timedelta(days=180)).isoformat() + 'Z'  # 6 months
                
                payloads = []
                article_id = article['url'].split('/')[-1][:50]
                
                for i, chunk_text in enumerate(chunks):
                    chunk_tokens = len(chunker.encoding.encode(chunk_text))
                    payloads.append({
                        'chunk_id': f"{ticker}_news_{article_id}_{i}",
                        'ticker': ticker,
                        'company': company_name,
                        'data_source': 'news',
                        'article_title': article['title'],
                        'article_url': article['url'],
                        'published_date': pub_date.isoformat() + 'Z',
                        'relevance_score': article.get('relevance_score', 0.0),
                        'chunk_text': chunk_text,
                        'chunk_tokens': chunk_tokens,
                        'created_at': current_time,
                        'expires_at': expires_at
                    })
                
                qdrant.upload_vectors(collection_name=collection_name, vectors=embeddings, payloads=payloads)
                
                print(f"   ✓ {article['title'][:50]}... ({len(chunks)} chunks)")
            
            total_articles += len(articles)
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\n✅ Processed {total_articles} article(s), {total_chunks} chunk(s) total")
    
    return {'articles': total_articles, 'chunks': total_chunks}


def cleanup_old_news(**context):
    """Delete news articles older than 6 months"""
    import sys
    from pathlib import Path
    import os
    from dotenv import load_dotenv
    
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    load_dotenv()
    
    from src.cloud import QdrantConnector
    from qdrant_client.http import models
    
    print("\n🗑️  Cleaning up old news articles...")
    
    # Initialize Qdrant
    qdrant = QdrantConnector(
        url=os.getenv('QDRANT_URL'),
        api_key=os.getenv('QDRANT_API_KEY')
    )
    
    collection_name = os.getenv('QDRANT_COLLECTION', 'company_data')
    
    # Calculate cutoff date (6 months ago)
    cutoff_date = (datetime.utcnow() - timedelta(days=180)).isoformat() + 'Z'
    
    print(f"   Deleting news older than: {cutoff_date}")
    
    try:
        # Delete points where data_source = 'news' AND expires_at < cutoff_date
        # Note: Qdrant filtering syntax for deletion
        qdrant.client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="data_source",
                            match=models.MatchValue(value="news")
                        ),
                        models.FieldCondition(
                            key="expires_at",
                            range=models.Range(
                                lt=cutoff_date
                            )
                        )
                    ]
                )
            )
        )
        
        print(f"   ✅ Cleanup complete")
        
    except Exception as e:
        print(f"   ⚠️  Cleanup failed: {e}")
        # Don't fail the DAG if cleanup fails
    
    return "cleanup_complete"


# DAG Tasks
start = DummyOperator(task_id='start', dag=dag)

fetch_task = PythonOperator(
    task_id='fetch_news',
    python_callable=fetch_news_articles,
    provide_context=True,
    execution_timeout=timedelta(hours=1),
    dag=dag,
)

cleanup_task = PythonOperator(
    task_id='cleanup_old_news',
    python_callable=cleanup_old_news,
    provide_context=True,
    execution_timeout=timedelta(minutes=10),
    dag=dag,
)

end = DummyOperator(task_id='end', dag=dag)

# Dependencies
start >> fetch_task >> cleanup_task >> end
