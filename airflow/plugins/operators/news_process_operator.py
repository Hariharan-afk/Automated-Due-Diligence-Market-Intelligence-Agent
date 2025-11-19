# airflow/plugins/operators/news_process_operator.py
"""Custom operator for news article processing"""

from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from typing import Any
import sys

sys.path.insert(0, '/opt/airflow')


class NewsProcessOperator(BaseOperator):
    """Airflow operator for news article processing"""
    
    template_fields = ['ticker']
    ui_color = '#E74C3C'
    ui_fgcolor = '#FFFFFF'
    
    @apply_defaults
    def __init__(self, ticker: str, days_back: int = 3, **kwargs):
        super().__init__(**kwargs)
        self.ticker = ticker
        self.days_back = days_back
    
    def execute(self, context: Any) -> str:
        """Execute news processing"""
        
        # ✅ Import heavy libraries INSIDE execute()
        from src.data_ingestion.news_fetcher import NewsFetcher
        from src.data_processing.news_parser import NewsParser
        from src.data_processing.text_cleaner import TextCleaner
        from src.data_processing.chunking_engine import ChunkingEngine
        from src.data_processing.metadata_enricher import MetadataEnricher
        from src.embeddings.embedding_generator import EmbeddingGenerator
        from src.storage.metadata_store_manager import MetadataStoreManager
        from src.storage.vector_store_manager import VectorStoreManager
        from src.storage.blob_storage_manager import BlobStorageManager
        
        self.log.info(f"Processing news for {self.ticker}")
        
        # Initialize components
        fetcher = NewsFetcher(mode="gdelt")
        parser = NewsParser()
        cleaner = TextCleaner()
        chunker = ChunkingEngine()
        enricher = MetadataEnricher()
        embedder = EmbeddingGenerator()
        
        metadata_store = MetadataStoreManager()
        vector_store = VectorStoreManager()
        blob_storage = BlobStorageManager()
        
        try:
            # Fetch articles
            self.log.info(f"Fetching news (last {self.days_back} days)")
            
            try:
                articles = fetcher.fetch_by_ticker(self.ticker, days_back=self.days_back)
            except:
                self.log.warning("GDELT failed, using mock mode")
                fetcher = NewsFetcher(mode="mock")
                articles = fetcher.fetch_by_ticker(self.ticker, days_back=self.days_back)
            
            if not articles:
                self.log.info("No articles found")
                metadata_store.close()
                return "no_articles"
            
            self.log.info(f"Found {len(articles)} articles")
            
            # Process each article
            total_chunks = 0
            
            for article in articles:
                try:
                    # Save article metadata
                    article_id = metadata_store.save_news_article(
                        ticker=self.ticker,
                        article_url=article['url'],
                        title=article['title'],
                        source=article['source'],
                        published_date=article['published_date'],
                        retention_days=3
                    )
                    
                    if not article_id:
                        continue
                    
                    # Parse article
                    if article.get('html_content'):
                        parsed = parser.parse(article['html_content'], article['url'], article['title'])
                        article_text = parsed['body']
                    else:
                        article_text = f"{article['title']}. {article.get('description', '')}"
                    
                    # Clean
                    clean_text = cleaner.clean(article_text, source_type="news", verify_english=True)
                    
                    if not clean_text or len(clean_text) < 100:
                        continue
                    
                    # Chunk
                    chunks = chunker.chunk_text(clean_text, section_header=f"News - {article['title'][:50]}")
                    
                    # Enrich
                    news_metadata = enricher.create_source_metadata_news(
                        ticker=self.ticker,
                        article_url=article['url'],
                        article_title=article['title'],
                        published_date=article['published_date'],
                        source=article['source'],
                        article_id=article_id
                    )
                    
                    enriched_chunks = enricher.enrich_chunks(chunks, news_metadata)
                    
                    # Embed
                    chunks_with_embeddings = embedder.embed_chunks(enriched_chunks)
                    
                    # Store
                    vector_store.upsert_chunks(chunks_with_embeddings)
                    metadata_store.mark_news_indexed(article_id, len(chunks_with_embeddings))
                    
                    blob_storage.save_news_article(
                        ticker=self.ticker,
                        article_id=str(article_id),
                        content=clean_text,
                        published_date=article['published_date'].strftime('%Y-%m-%d')
                    )
                    
                    total_chunks += len(chunks_with_embeddings)
                
                except Exception as e:
                    self.log.warning(f"Failed to process article: {e}")
                    continue
            
            self.log.info(f"✅ Processed {total_chunks} total chunks")
            
            metadata_store.close()
            
            return f"processed_{total_chunks}_chunks"
        
        except Exception as e:
            self.log.error(f"Failed: {e}")
            if metadata_store:
                metadata_store.close()
            raise