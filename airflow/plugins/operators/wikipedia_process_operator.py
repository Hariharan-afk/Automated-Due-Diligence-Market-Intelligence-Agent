# airflow/plugins/operators/wikipedia_process_operator.py
"""Custom operator for Wikipedia page processing"""

from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from typing import Any
import sys

sys.path.insert(0, '/opt/airflow')


class WikipediaProcessOperator(BaseOperator):
    """Airflow operator for Wikipedia page processing"""
    
    template_fields = ['ticker']
    ui_color = '#4A90E2'
    ui_fgcolor = '#FFFFFF'
    
    @apply_defaults
    def __init__(self, ticker: str, **kwargs):
        super().__init__(**kwargs)
        self.ticker = ticker
    
    def execute(self, context: Any) -> str:
        """Execute Wikipedia processing"""
        
        # ✅ Import heavy libraries INSIDE execute() - only loads when task runs
        from src.data_ingestion.wikipedia_fetcher import WikipediaFetcher
        from src.data_processing.wikipedia_parser import WikipediaParser
        from src.data_processing.text_cleaner import TextCleaner
        from src.data_processing.chunking_engine import ChunkingEngine
        from src.data_processing.metadata_enricher import MetadataEnricher
        from src.embeddings.embedding_generator import EmbeddingGenerator
        from src.storage.metadata_store_manager import MetadataStoreManager
        from src.storage.vector_store_manager import VectorStoreManager
        from src.storage.blob_storage_manager import BlobStorageManager
        from src.utils.config import config
        
        self.log.info(f"Processing Wikipedia for {self.ticker}")
        
        # Initialize all components
        fetcher = WikipediaFetcher()
        parser = WikipediaParser()
        cleaner = TextCleaner()
        chunker = ChunkingEngine()
        enricher = MetadataEnricher()
        embedder = EmbeddingGenerator()
        
        metadata_store = MetadataStoreManager()
        vector_store = VectorStoreManager()
        blob_storage = BlobStorageManager()
        
        try:
            # Get company info
            company = config.get_company_by_ticker(self.ticker)
            page_title = company['name']
            
            # Check if changed
            stored_revision = metadata_store.get_wikipedia_revision(self.ticker)
            
            if stored_revision:
                has_changed = fetcher.has_page_changed(page_title, stored_revision)
                
                if not has_changed:
                    self.log.info(f"Page unchanged for {self.ticker} - skipping")
                    metadata_store.close()
                    return "unchanged"
            
            # Fetch
            self.log.info(f"Fetching Wikipedia page for {self.ticker}")
            wiki_data = fetcher.fetch_by_ticker(self.ticker)
            
            # Parse
            self.log.info(f"Parsing structure")
            parsed = parser.parse(wiki_data['html_content'], wiki_data['page_title'])
            
            # Clean
            self.log.info(f"Cleaning text")
            clean_intro = cleaner.clean(parsed['intro'], source_type="wikipedia", verify_english=True)
            
            if not clean_intro:
                self.log.warning(f"Non-English content - skipping")
                metadata_store.close()
                return "non_english"
            
            clean_sections = []
            for section in parsed['sections']:
                clean_content = cleaner.clean(section['content'], source_type="wikipedia", verify_english=True)
                if clean_content:
                    clean_sections.append({
                        'title': cleaner.clean(section['title'], source_type="wikipedia"),
                        'content': clean_content
                    })
            
            # Chunk
            self.log.info(f"Chunking text")
            all_chunks = []
            
            intro_chunks = chunker.chunk_text(clean_intro, section_header="Introduction")
            all_chunks.extend(intro_chunks)
            
            for section in clean_sections:
                section_chunks = chunker.chunk_text(section['content'], section_header=section['title'])
                all_chunks.extend(section_chunks)
            
            self.log.info(f"Created {len(all_chunks)} chunks")
            
            # Enrich with metadata
            source_metadata = enricher.create_source_metadata_wikipedia(
                ticker=self.ticker,
                page_title=wiki_data['page_title'],
                revision_id=wiki_data['revision_id'],
                page_url=wiki_data['page_url']
            )
            
            enriched_chunks = enricher.enrich_chunks(all_chunks, source_metadata)
            
            # Generate embeddings
            self.log.info(f"Generating embeddings")
            chunks_with_embeddings = embedder.embed_chunks(enriched_chunks)
            
            # Delete old data
            if stored_revision:
                self.log.info(f"Deleting old Wikipedia data")
                vector_store.delete_by_ticker(self.ticker, source_type="wikipedia")
            
            # Store new data
            self.log.info(f"Storing {len(chunks_with_embeddings)} chunks")
            vector_store.upsert_chunks(chunks_with_embeddings)
            
            metadata_store.save_wikipedia_metadata(
                ticker=self.ticker,
                page_title=wiki_data['page_title'],
                page_url=wiki_data['page_url'],
                revision_id=wiki_data['revision_id'],
                chunk_count=len(chunks_with_embeddings)
            )
            
            metadata_store.mark_wikipedia_indexed(self.ticker)
            
            blob_storage.save_wikipedia_page(
                ticker=self.ticker,
                page_title=wiki_data['page_title'],
                content=wiki_data['html_content'],
                revision_id=wiki_data['revision_id']
            )
            
            self.log.info(f"✅ Completed: {len(chunks_with_embeddings)} chunks stored")
            
            metadata_store.close()
            
            return f"processed_{len(chunks_with_embeddings)}_chunks"
        
        except Exception as e:
            self.log.error(f"Failed: {e}")
            if metadata_store:
                metadata_store.close()
            raise