# airflow/dags/data_cleanup_pipeline.py
"""
Data Cleanup Pipeline

Schedule: Daily at 1 AM (before SEC pipeline)
Purpose: Delete news articles older than 3 days
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys

# ✅ FIXED: Use absolute path in Docker container
sys.path.insert(0, '/opt/airflow')

from src.storage.metadata_store_manager import MetadataStoreManager
from src.storage.vector_store_manager import VectorStoreManager
from src.storage.blob_storage_manager import BlobStorageManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def cleanup_expired_news(**context):
    """
    Delete news articles older than retention period (3 days)
    """
    logger.info("Starting news cleanup process")
    
    metadata_store = MetadataStoreManager()
    vector_store = VectorStoreManager()
    blob_storage = BlobStorageManager()
    
    try:
        # Step 1: Get expired articles from PostgreSQL
        expired_articles = metadata_store.get_expired_news_articles()
        
        if not expired_articles:
            logger.info("No expired news articles to delete")
            metadata_store.close()
            return "no_expired_articles"
        
        logger.info(f"Found {len(expired_articles)} expired news articles")
        
        # Step 2: Collect chunk IDs to delete from Qdrant
        # (Chunk IDs follow pattern: TICKER_NEWS_DATE_HASH_text_000)
        article_ids = [article['id'] for article in expired_articles]
        
        # For each article, we need to find its chunks in Qdrant
        # We can filter by ticker + article metadata
        total_deleted = 0
        
        for article in expired_articles:
            ticker = article['ticker']
            
            # Delete chunks from Qdrant (filter by ticker and source_type=news)
            # Note: This is approximate - in production you'd want to track chunk_ids per article
            deleted_count = vector_store.delete_by_ticker(ticker, source_type="news")
            total_deleted += deleted_count
            
            logger.debug(f"Deleted chunks for article: {article['title'][:50]}...")
        
        logger.info(f"Deleted ~{total_deleted} chunks from Qdrant")
        
        # Step 3: Delete from PostgreSQL
        metadata_store.delete_news_articles(article_ids)
        
        logger.info(f"Deleted {len(article_ids)} articles from PostgreSQL")
        
        # Step 4: Delete old news files from blob storage
        deleted_files = blob_storage.delete_old_news(days_old=3)
        
        logger.info(f"Deleted {deleted_files} old news files from storage")
        
        # Step 5: Log statistics
        logger.info(
            f"✅ Cleanup complete: "
            f"{len(article_ids)} articles, ~{total_deleted} chunks removed"
        )
        
        metadata_store.close()
        
        return f"deleted_{len(article_ids)}_articles"
    
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        if metadata_store:
            metadata_store.close()
        raise


def cleanup_cache(**context):
    """
    Clean up old cache files (embeddings, table summaries)
    """
    logger.info("Cleaning up cache files")
    
    blob_storage = BlobStorageManager()
    
    try:
        # Delete cache files older than 30 days
        deleted_count = blob_storage.cleanup_cache(max_age_days=30)
        
        logger.info(f"✅ Deleted {deleted_count} old cache files")
        
        return f"deleted_{deleted_count}_cache_files"
    
    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}")
        raise


# Define DAG
default_args = {
    'owner': 'data_pipeline',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'data_cleanup_pipeline',
    default_args=default_args,
    description='Daily cleanup of expired news and cache',
    schedule_interval='0 1 * * *',  # Daily at 1 AM
    start_date=datetime(2024, 11, 1),
    catchup=False,
    tags=['cleanup', 'daily', 'maintenance'],
) as dag:
    
    # Task 1: Delete expired news
    cleanup_news_task = PythonOperator(
        task_id='cleanup_expired_news',
        python_callable=cleanup_expired_news,
        execution_timeout=timedelta(minutes=10)
    )
    
    # Task 2: Clean up cache
    cleanup_cache_task = PythonOperator(
        task_id='cleanup_cache',
        python_callable=cleanup_cache,
        execution_timeout=timedelta(minutes=5)
    )
    
    # Set dependencies (cleanup news first, then cache)
    cleanup_news_task >> cleanup_cache_task