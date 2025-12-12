# src/data_processing/news_processor.py
"""News article processor - orchestrates the complete news workflow"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data_ingestion.news_fetcher import NewsFetcher
from src.data_processing.embedder import FinancialEmbedder
from src.storage.postgres_manager import PostgresManager
from src.storage.qdrant_manager import QdrantManager
from src.utils.config import config
from src.utils.logging_config import get_logger
from langchain.text_splitter import RecursiveCharacterTextSplitter

logger = get_logger(__name__)


class NewsProcessor:
    """
    Orchestrates the complete news article processing workflow
    
    Workflow:
    1. Fetch recent news articles (NewsAPI + Newspaper3k)
    2. Deduplicate and filter by relevance
    3. Each article stored as single data point (no chunking)
    4. Embed full article content (FinE5)
    5. Store in Qdrant + PostgreSQL
    6. Cleanup expired articles (>3 days old)
    """
    
    def __init__(
        self,
        postgres_manager: PostgresManager,
        qdrant_manager: QdrantManager,
        embedder: FinancialEmbedder
    ):
        """
        Initialize News processor
        
        Args:
            postgres_manager: PostgreSQL manager instance
            qdrant_manager: Qdrant manager instance
            embedder: Embedder instance
        """
        self.postgres = postgres_manager
        self.qdrant = qdrant_manager
        self.embedder = embedder
        
        # Initialize components
        self.fetcher = NewsFetcher()
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=768,
            chunk_overlap=256,
            length_function=len,
            is_separator_regex=False,
        )
        
        logger.info("NewsProcessor initialized")
    
    def process_company_news(
        self,
        ticker: str,
        days_back: int = 7,
        max_articles: int = 20,
        relevance_threshold: float = 0.6
    ) -> Dict[str, Any]:
        """
        Process news articles for a single company
        
        Args:
            ticker: Company ticker
            days_back: Number of days to look back for news
            max_articles: Maximum number of articles to fetch
            relevance_threshold: Minimum relevance score (0.0-1.0)
        
        Returns:
            Processing result dict
        """
        logger.info(f"Processing news for {ticker} (last {days_back} days)")
        
        # Get company info
        company = config.get_company_by_ticker(ticker)
        if not company:
            raise ValueError(f"Company {ticker} not found in config")
        
        try:
            # Fetch articles
            logger.info(f"Fetching articles for {ticker}...")
            articles = self.fetcher.fetch_by_ticker(
                ticker=ticker,
                days_back=days_back,
                max_records=max_articles,
                relevance_threshold=relevance_threshold
            )
            
            if not articles:
                logger.warning(f"No articles found for {ticker}")
                return {
                    'status': 'success',
                    'ticker': ticker,
                    'articles_fetched': 0,
                    'articles_processed': 0,
                    'articles_failed': 0
                }
            
            logger.info(f"Fetched {len(articles)} articles for {ticker}")
            
            # Process each article
            processed_count = 0
            failed_count = 0
            
            for article in articles:
                try:
                    # Check if article already exists in database
                    existing = self.postgres.execute_query(
                        "SELECT id FROM news_metadata WHERE article_url = %s",
                        (article['url'],),
                        fetch=True
                    )
                    
                    if existing:
                        logger.debug(f"Article already exists: {article['title'][:50]}...")
                        continue
                    
                    # Extract content
                    content = article.get('content', '')
                    
                    # Skip if no content or too short
                    if not content or len(content) < 100:
                        logger.warning(f"Skipping article with insufficient content: {article['title'][:50]}...")
                        failed_count += 1
                        continue
                    
                    # Calculate expiry date (3 days from publication)
                    published_date = article.get('published_date')
                    if published_date and isinstance(published_date, datetime):
                        expires_at = published_date + timedelta(days=3)
                    else:
                        # If no published date, use current time + 3 days
                        expires_at = datetime.now() + timedelta(days=3)
                    
                    # Insert article metadata into PostgreSQL
                    article_data = {
                        'ticker': ticker,
                        'company_name': company.name,
                        'article_url': article['url'],
                        'title': article.get('title', 'Unknown'),
                        'source': article.get('source', 'Unknown'),
                        'author': article.get('author', 'Unknown'),
                        'published_date': published_date,
                        'relevance_score': article.get('relevance_score', 0.0),
                        'expires_at': expires_at
                    }
                    
                    article_id = self.postgres.insert_news_article(article_data)
                    self.postgres.update_news_status(article_id, 'processing')
                    
                    # Chunk the content
                    chunks = self.text_splitter.split_text(content)
                    logger.debug(f"Split article into {len(chunks)} chunks")

                    # Embed all chunks
                    logger.debug(f"Embedding {len(chunks)} chunks for article: {article['title'][:50]}...")
                    embeddings = self.embedder.embed_chunks(chunks, show_progress=False)
                    
                    if not embeddings or len(embeddings) != len(chunks):
                        logger.error(f"Failed to embed article chunks: {article['title'][:50]}...")
                        self.postgres.update_news_status(
                            article_id, 
                            'failed', 
                            error='Embedding failed'
                        )
                        failed_count += 1
                        continue
                    
                    # Prepare chunks for Qdrant
                    qdrant_chunks = []
                    for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                        # Generate chunk ID
                        chunk_id = QdrantManager.generate_chunk_id(
                            ticker=ticker,
                            source='news',
                            content=chunk_text,
                            index=i
                        )
                        
                        # Prepare metadata for Qdrant
                        metadata = {
                            'data_source_type': 'news',
                            'fetched_date': datetime.now().isoformat(),
                            'ticker': ticker,
                            'company_name': company.name,
                            'article_title': article.get('title', 'Unknown'),
                            'article_url': article['url'],
                            'news_source': article.get('source', 'Unknown'),
                            'published_date': published_date.isoformat() if isinstance(published_date, datetime) else str(published_date),
                            'relevance_score': article.get('relevance_score', 0.0),
                            'chunk_length': len(chunk_text),
                            'chunk_index': i,
                            'total_chunks': len(chunks),
                            'expires_at': expires_at.isoformat()
                        }
                        
                        # Store in Qdrant
                        qdrant_chunks.append({
                            'chunk_id': chunk_id,
                            'vector': embedding,
                            'raw_chunk': chunk_text,
                            'metadata': metadata
                        })
                    
                    self.qdrant.upsert_chunks(qdrant_chunks, batch_size=10)
                    
                    # Update status in PostgreSQL
                    self.postgres.update_news_status(
                        article_id=article_id,
                        status='completed',
                        chunks=len(chunks)
                    )
                    
                    processed_count += 1
                    logger.debug(f"✓ Processed article: {article['title'][:50]}...")
                    
                except Exception as e:
                    logger.error(f"Failed to process article {article.get('url', 'Unknown')}: {e}")
                    failed_count += 1
            
            result = {
                'status': 'success',
                'ticker': ticker,
                'articles_fetched': len(articles),
                'articles_processed': processed_count,
                'articles_failed': failed_count
            }
            
            logger.info(f"✓ Completed {ticker}: {processed_count} processed, {failed_count} failed")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process news for {ticker}: {e}", exc_info=True)
            return {
                'status': 'failed',
                'ticker': ticker,
                'error': str(e)
            }
    
    def cleanup_expired_news(self) -> Dict[str, Any]:
        """
        Cleanup news articles older than 3 days
        
        Returns:
            Cleanup summary dict
        """
        logger.info("Cleaning up expired news articles...")
        
        try:
            # Get expired articles from PostgreSQL
            expired_articles = self.postgres.get_expired_news_articles()
            
            if not expired_articles:
                logger.info("No expired articles to clean up")
                return {
                    'status': 'success',
                    'articles_deleted': 0
                }
            
            logger.info(f"Found {len(expired_articles)} expired articles")
            
            deleted_count = 0
            
            for article in expired_articles:
                try:
                    ticker = article['ticker']
                    article_url = article['article_url']
                    article_id = article['id']
                    
                    # Delete from Qdrant (filter by ticker and URL)
                    self.qdrant.delete_by_filter({
                        'ticker': ticker,
                        'data_source_type': 'news',
                        'article_url': article_url
                    })
                    
                    # Delete from PostgreSQL
                    self.postgres.delete_news_article(article_id)
                    
                    deleted_count += 1
                    logger.debug(f"Deleted expired article: {article.get('title', 'Unknown')[:50]}...")
                    
                except Exception as e:
                    logger.error(f"Failed to delete article {article.get('article_url', 'Unknown')}: {e}")
            
            logger.info(f"✓ Cleaned up {deleted_count} expired articles")
            
            return {
                'status': 'success',
                'articles_deleted': deleted_count
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired news: {e}", exc_info=True)
            return {
                'status': 'failed',
                'error': str(e),
                'articles_deleted': 0
            }
    
    def process_and_cleanup(
        self,
        days_back: int = 7,
        max_articles_per_company: int = 20,
        relevance_threshold: float = 0.6
    ) -> Dict[str, Any]:
        """
        Process new news articles for all companies and cleanup expired ones
        
        Args:
            days_back: Number of days to look back for news
            max_articles_per_company: Max articles per company
            relevance_threshold: Min relevance score
        
        Returns:
            Combined processing and cleanup summary
        """
        logger.info("=" * 80)
        logger.info("NEWS PROCESSING & CLEANUP")
        logger.info("=" * 80)
        
        # Get all company tickers
        tickers = config.get_all_tickers()
        
        # Process news for each company
        processing_results = {
            'companies_processed': 0,
            'total_articles': 0,
            'total_processed': 0,
            'total_failed': 0,
            'details': []
        }
        
        for ticker in tickers:
            logger.info(f"\n--- Processing {ticker} ---")
            
            try:
                result = self.process_company_news(
                    ticker=ticker,
                    days_back=days_back,
                    max_articles=max_articles_per_company,
                    relevance_threshold=relevance_threshold
                )
                
                processing_results['companies_processed'] += 1
                processing_results['total_articles'] += result.get('articles_fetched', 0)
                processing_results['total_processed'] += result.get('articles_processed', 0)
                processing_results['total_failed'] += result.get('articles_failed', 0)
                processing_results['details'].append(result)
                
            except Exception as e:
                logger.error(f"Failed to process news for {ticker}: {e}")
                processing_results['total_failed'] += 1
        
        # Cleanup expired articles
        logger.info("\n" + "=" * 80)
        logger.info("CLEANUP EXPIRED ARTICLES")
        logger.info("=" * 80)
        
        cleanup_result = self.cleanup_expired_news()
        
        # Combined summary
        summary = {
            'processing': processing_results,
            'cleanup': cleanup_result
        }
        
        logger.info("\n" + "=" * 80)
        logger.info("NEWS TASK SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Companies processed: {processing_results['companies_processed']}")
        logger.info(f"Articles fetched: {processing_results['total_articles']}")
        logger.info(f"Articles processed: {processing_results['total_processed']}")
        logger.info(f"Articles failed: {processing_results['total_failed']}")
        logger.info(f"Articles cleaned up: {cleanup_result['articles_deleted']}")
        logger.info("=" * 80 + "\n")
        
        return summary
