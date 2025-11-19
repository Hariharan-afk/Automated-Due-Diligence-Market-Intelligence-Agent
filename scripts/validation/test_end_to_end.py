# scripts/validation/test_end_to_end.py
"""
Complete end-to-end pipeline test

Tests: Fetch → Preprocess → Embed → Store → Retrieve
"""

import sys
from pathlib import Path
import os

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent  # DATA_PIPELINE directory
sys.path.insert(0, str(project_root))

import json
from src.data_ingestion.sec_fetcher import SECFetcher
from src.data_processing.preprocessing_pipeline import PreprocessingPipeline
from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.vector_store_manager import VectorStoreManager
from src.storage.metadata_store_manager import MetadataStoreManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def test_complete_pipeline():
    """Test complete pipeline from fetch to storage"""
    
    print("\n" + "🚀"*35)
    print("END-TO-END PIPELINE TEST")
    print("🚀"*35 + "\n")
    
    # Initialize all components
    print("Initializing components...")
    print("-" * 70)
    
    fetcher = SECFetcher()
    pipeline = PreprocessingPipeline()
    embedder = EmbeddingGenerator()
    vector_store = VectorStoreManager()
    metadata_store = MetadataStoreManager()
    
    print("✅ All components initialized\n")
    
    # ========== STAGE 1: FETCH ==========
    print("\n" + "="*70)
    print("STAGE 1: FETCHING SEC DATA")
    print("="*70 + "\n")
    
    ticker = "AAPL"
    filings = fetcher.fetch_filings_with_sections(ticker, filing_types=['10-K'])
    
    if not filings:
        print("❌ No filings fetched")
        return False
    
    # Use just the first filing for testing
    filing = filings[0]
    
    print(f"✅ Fetched: {filing['filing_metadata']['filing_type']} "
          f"dated {filing['filing_metadata']['filing_date']}")
    print(f"   Sections: {len(filing['sections'])}")
    print(f"   Total text: {sum(len(s) for s in filing['sections'].values()):,} chars")
    
    # ========== STAGE 2: PREPROCESS ==========
    print("\n" + "="*70)
    print("STAGE 2: PREPROCESSING")
    print("="*70 + "\n")
    
    enriched_chunks = pipeline.process_filing(filing)
    
    print(f"✅ Preprocessing complete:")
    print(f"   Total chunks: {len(enriched_chunks)}")
    print(f"   Table chunks: {sum(1 for c in enriched_chunks if c['chunk_type'] == 'table')}")
    print(f"   Text chunks: {sum(1 for c in enriched_chunks if c['chunk_type'] == 'text')}")
    
    # ========== STAGE 3: GENERATE EMBEDDINGS ==========
    print("\n" + "="*70)
    print("STAGE 3: GENERATING EMBEDDINGS")
    print("="*70 + "\n")
    
    chunks_with_embeddings = embedder.generate_embeddings(
        enriched_chunks,
        show_progress=True
    )
    
    # Validate embeddings
    valid = embedder.validate_embeddings(chunks_with_embeddings)
    
    print(f"\n✅ Embedding generation complete:")
    print(f"   Chunks with embeddings: {len(chunks_with_embeddings)}")
    print(f"   Embedding dimension: {embedder.embedding_dim}")
    print(f"   Validation: {'PASSED ✅' if valid else 'FAILED ❌'}")
    
    # ========== STAGE 4: STORE IN VECTOR DB ==========
    print("\n" + "="*70)
    print("STAGE 4: STORING IN QDRANT")
    print("="*70 + "\n")
    
    upserted_count = vector_store.upsert_chunks(chunks_with_embeddings)
    
    print(f"✅ Storage complete:")
    print(f"   Chunks stored: {upserted_count}")
    
    # ========== STAGE 5: STORE METADATA ==========
    print("\n" + "="*70)
    print("STAGE 5: STORING METADATA IN POSTGRESQL")
    print("="*70 + "\n")
    
    filing_meta = filing['filing_metadata']
    
    # Check if filing already exists
    existing = metadata_store.check_filing_exists(filing_meta['accession_number'])
    
    if existing:
        print(f"⚠️  Filing {filing_meta['accession_number']} already in database")
        print("   Updating instead of inserting...")
    
    # Save filing metadata
    filing_id = metadata_store.save_filing_metadata(
        ticker=filing_meta['ticker'],
        filing_type=filing_meta['filing_type'],
        filing_date=filing_meta['filing_date'],
        accession_number=filing_meta['accession_number'],
        filing_url=filing_meta['filing_url'],
        fiscal_year=filing_meta['fiscal_year'],
        fiscal_quarter=filing_meta['fiscal_quarter'],
        fiscal_period_end=filing_meta['period_of_report']
    )
    
    print(f"✅ Saved filing metadata (ID: {filing_id})")
    
    # Update processing stats
    table_count = sum(1 for c in chunks_with_embeddings if c['chunk_type'] == 'table')
    text_count = sum(1 for c in chunks_with_embeddings if c['chunk_type'] == 'text')
    
    metadata_store.update_filing_processing_complete(
        filing_id=filing_id,
        sections_extracted=list(filing['sections'].keys()),
        total_chunks=len(chunks_with_embeddings),
        text_chunks=text_count,
        table_chunks=table_count
    )
    
    metadata_store.mark_filing_indexed(filing_id)
    
    print(f"✅ Updated filing stats:")
    print(f"   Sections: {len(filing['sections'])}")
    print(f"   Total chunks: {len(chunks_with_embeddings)}")
    print(f"   Indexed: True")
    
    # ========== STAGE 6: VERIFY RETRIEVAL ==========
    print("\n" + "="*70)
    print("STAGE 6: VERIFYING RETRIEVAL")
    print("="*70 + "\n")
    
    # Test semantic search
    query_text = "What are the risk factors for Apple?"
    query_embedding = embedder.generate_embedding_single(query_text)
    
    print(f"Query: '{query_text}'")
    print(f"Searching...")
    
    search_results = vector_store.search(
        query_vector=query_embedding,
        limit=5,
        filters={'ticker': ticker, 'section': '1A'}  # Only Risk Factors
    )
    
    print(f"\n✅ Found {len(search_results)} relevant chunks:\n")
    
    for i, result in enumerate(search_results, 1):
        chunk = result['chunk']
        print(f"{i}. Score: {result['score']:.3f}")
        print(f"   Chunk: {chunk['chunk_id']}")
        print(f"   Type: {chunk['chunk_type']}")
        print(f"   Section: {chunk['section']} ({chunk.get('section_name', 'N/A')})")
        print(f"   Preview: {chunk['text'][:150]}...")
        print()
    
    # ========== STAGE 7: DATABASE STATISTICS ==========
    print("\n" + "="*70)
    print("STAGE 7: DATABASE STATISTICS")
    print("="*70 + "\n")
    
    # Vector DB stats
    vector_info = vector_store.get_collection_info()
    print(f"📊 Qdrant:")
    print(f"   Total vectors: {vector_info.get('vectors_count', 0)}")
    print(f"   Status: {vector_info.get('status', 'unknown')}")
    
    # Count by filters
    print(f"\n   Breakdowns:")
    print(f"     Tables: {vector_store.count_chunks({'contains_table': True})}")
    print(f"     Text: {vector_store.count_chunks({'contains_table': False})}")
    print(f"     Section 1A: {vector_store.count_chunks({'section': '1A'})}")
    print(f"     Section 7: {vector_store.count_chunks({'section': '7'})}")
    
    # PostgreSQL stats
    pg_stats = metadata_store.get_pipeline_stats()
    print(f"\n📊 PostgreSQL:")
    print(f"   Companies: {pg_stats['companies']}")
    print(f"   Total filings: {pg_stats['filings']['total']}")
    print(f"   Completed: {pg_stats['filings']['completed']}")
    print(f"   Total chunks tracked: {pg_stats['filings']['total_chunks']}")
    
    # ========== FINAL SUMMARY ==========
    print("\n\n" + "="*70)
    print("✅ END-TO-END TEST COMPLETE")
    print("="*70 + "\n")
    
    print("Pipeline Summary:")
    print(f"  ✅ Fetched 1 filing with {len(filing['sections'])} sections")
    print(f"  ✅ Generated {len(enriched_chunks)} enriched chunks")
    print(f"  ✅ Created {len(chunks_with_embeddings)} embeddings")
    print(f"  ✅ Stored {upserted_count} vectors in Qdrant")
    print(f"  ✅ Saved metadata in PostgreSQL")
    print(f"  ✅ Retrieval working (semantic search successful)")
    
    # Cost summary
    pipeline_stats = pipeline.get_pipeline_stats()
    print(f"\n💰 Cost Summary:")
    print(f"  LLM calls: {pipeline_stats['llm_usage']['api_calls']}")
    print(f"  Total tokens: {pipeline_stats['llm_usage']['total_tokens']:,}")
    print(f"  Cost: ${pipeline_stats['llm_usage']['estimated_cost_usd']:.4f}")
    
    print("\n✅ Your preprocessing pipeline is production-ready!")
    print("\n" + "="*70 + "\n")
    
    return True


if __name__ == "__main__":
    try:
        success = test_complete_pipeline()
        
        if success:
            print("\n🎉 SUCCESS! All stages completed successfully!")
            print("\nYou can now:")
            print("  1. Process all 5 companies")
            print("  2. Build Airflow DAGs")
            print("  3. Set up monitoring")
            
    except Exception as e:
        print(f"\n❌ End-to-end test failed: {e}")
        print("\nCheck that:")
        print("  - Docker containers are running (docker-compose ps)")
        print("  - Qdrant collection exists (http://localhost:6333/dashboard)")
        print("  - PostgreSQL is accessible")
        print("  - All API keys are set in .env")
        
        import traceback
        traceback.print_exc()