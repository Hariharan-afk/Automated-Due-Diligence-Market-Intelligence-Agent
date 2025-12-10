"""
End-to-End Pipeline Test

Tests the complete production pipeline flow:
1. Fetch SEC filing for AAPL (one recent 10-K)
2. Process sections and extract tables
3. Chunk text with LangChain
4. Generate embeddings with BGE-large-en-v1.5
5. Upload raw data to GCS
6. Upload vectors to Qdrant with metadata
7. Track in PostgreSQL state management
8. Test semantic search retrieval

This validates the entire infrastructure is working together.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import json
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_ingestion.sec_fetcher import SECFetcher
from src.data_processing.chunker import TextChunker
from src.data_processing.table_processor import TableProcessor
from src.utils.table_summarizer import GroqTableSummarizer
from src.embedding import Embedder
from src.cloud import GCSConnector, PostgresConnector, QdrantConnector
from src.state import StateManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Load environment variables
load_dotenv()


def main():
    """Run end-to-end pipeline test"""
    
    print("=" * 80)
    print("END-TO-END PRODUCTION PIPELINE TEST")
    print("=" * 80)
    print()
    
    # Configuration
    ticker = "AAPL"
    company_name = "Apple Inc."
    cik = "0000320193"
    
    try:
        # ============================================================
        # STEP 1: Initialize All Components
        # ============================================================
        print("🔧 Step 1: Initializing components...")
        
        # Cloud connectors
        gcs = GCSConnector(
            bucket_name=os.getenv('GCP_BUCKET_NAME'),
            project_id=os.getenv('GCP_PROJECT_ID'),
            credentials_path=os.getenv('GCP_CREDENTIALS_PATH')
        )
        
        db = PostgresConnector(
            host=os.getenv('POSTGRES_HOST'),
            port=int(os.getenv('POSTGRES_PORT')),
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD')
        )
        
        qdrant = QdrantConnector(
            url=os.getenv('QDRANT_URL'),
            api_key=os.getenv('QDRANT_API_KEY')
        )
        
        # Processing components
        embedder = Embedder()
        chunker = TextChunker(
            chunk_size=512,
            overlap=128
        )
        
        # Table processing
        table_summarizer = GroqTableSummarizer(
            api_key=os.getenv('GROQ_API_KEY')
        )
        table_processor = TableProcessor(
            summarizer=table_summarizer,
            min_table_size=0  # Process all tables
        )
        
        # State management
        state = StateManager(db)
        
        print("✅ All components initialized")
        print()
        
        # ============================================================
        # STEP 2: Create Qdrant Collection (if needed)
        # ============================================================
        print("🗄️  Step 2: Setting up Qdrant collection...")
        
        collection_name = "company_data"
        
        # Create collection with proper configuration
        qdrant.create_collection(
            collection_name=collection_name,
            vector_size=1024,  # BGE-large-en-v1.5 dimension
            distance='Cosine',
            recreate=False  # Don't delete existing data
        )
        
        print(f"✅ Collection '{collection_name}' ready")
        print()
        
        # ============================================================
        # STEP 3: Fetch SEC Filing
        # ============================================================
        print(f"📄 Step 3: Fetching latest 10-K for {ticker}...")
        
        sec_fetcher = SECFetcher(user_identity=os.getenv('SEC_API_KEY', 'your.email@example.com'))
        
        filings = sec_fetcher.fetch_filings_by_cik(
            cik=cik,
            filing_types=['10-K'],
            start_date='2024-01-01',
            end_date='2024-12-31'
        )
        
        if not filings:
            print("❌ No filings found")
            return
        
        # Take the most recent filing
        filing = filings[0]
        
        print(f"✅ Fetched {filing['filing_type']} - {filing['filing_date']}")
        print(f"   Accession: {filing['accession_number']}")
        print(f"   Sections: {filing['total_sections']}")
        print(f"   Total length: {filing['total_length']:,} chars")
        print()
        
        # ============================================================
        # STEP 4: Track in PostgreSQL
        # ============================================================
        print("💾 Step 4: Tracking filing in PostgreSQL...")
        
        state.track_sec_filing(
            ticker=ticker,
            filing_type=filing['filing_type'],
            accession_number=filing['accession_number'],
            filing_date=filing['filing_date'],
            fiscal_year=filing['fiscal_year'],
            fiscal_quarter=filing.get('fiscal_quarter'),
            url=filing.get('filing_url'),
            status='processing'
        )
        
        print(f"✅ Filing tracked in database")
        print()
        
        # ============================================================
        # STEP 5: Process ONE Section (to keep test fast)
        # ============================================================
        print("⚙️  Step 5: Processing sections...")
        
        # Process only one section for testing speed
        test_section = filing['sections'][0]  # Usually Item 1 or similar
        
        section_metadata = {
            'ticker': ticker,
            'company': company_name,
            'filing_type': filing['filing_type'],
            'filing_year': filing['fiscal_year'],
            'fiscal_quarter': filing.get('fiscal_quarter'),
            'accession_number': filing['accession_number'],
            'section': test_section['section_code'],
            'section_name': test_section['section_name']
        }
        
        print(f"   Processing: {test_section['section_code']} - {test_section['section_name']}")
        print(f"   Length: {test_section['section_length']:,} chars")
        
        # Process tables
        processed_text, tables = table_processor.process_section(
            section_html=test_section.get('section_html_doc'),
            section_text=test_section['section_text'],
            metadata=section_metadata
        )
        
        print(f"   ✓ Extracted {len(tables)} tables")
        
        # Chunk the processed text
        chunks = chunker.chunk_text(processed_text)
        
        print(f"   ✓ Created {len(chunks)} chunks")
        print()
        
        # ============================================================
        # STEP 6: Generate Embeddings
        # ============================================================
        print("🧠 Step 6: Generating embeddings...")
        
        # Prepare chunk texts (chunks are already strings from TextChunker)
        chunk_texts = chunks
        
        # Generate embeddings (batch)
        embeddings = embedder.embed_documents(chunk_texts, batch_size=32)
        
        print(f"✅ Generated {len(embeddings)} embeddings ({embeddings.shape})")
        print()
        
        # ============================================================
        # STEP 7: Upload to GCS
        # ============================================================
        print("☁️  Step 7: Uploading to Google Cloud Storage...")
        
        # Create structured data
        raw_data = {
            'filing_metadata': {
                'ticker': ticker,
                'company': company_name,
                'filing_type': filing['filing_type'],
                'accession_number': filing['accession_number'],
                'filing_date': filing['filing_date'],
                'fiscal_year': filing['fiscal_year']
            },
            'section': {
                'code': test_section['section_code'],
                'name': test_section['section_name'],
                'length': test_section['section_length']
            },
            'tables': tables,
            'chunks': chunks,
            'total_chunks': len(chunks),
            'processed_at': datetime.utcnow().isoformat()
        }
        
        # Upload to GCS
        gcs_path = f"raw/sec/{ticker}/{filing['fiscal_year']}/{filing['accession_number']}_section_{test_section['section_code']}.json"
        
        gcs.upload_data(
            data=raw_data,
            gcs_path=gcs_path,
            metadata={
                'ticker': ticker,
                'filing_type': filing['filing_type'],
                'section': test_section['section_code']
            }
        )
        
        print(f"✅ Uploaded to: gs://{os.getenv('GCP_BUCKET_NAME')}/{gcs_path}")
        print()
        
        # ============================================================
        # STEP 8: Upload to Qdrant
        # ============================================================
        print("🔍 Step 8: Uploading vectors to Qdrant...")
        
        # Prepare payloads with full metadata
        payloads = []
        for i, chunk_text in enumerate(chunks):
            # Get token count for this chunk
            chunk_tokens = len(chunker.encoding.encode(chunk_text))
            
            payloads.append({
                'ticker': ticker,
                'company': company_name,
                'data_source': 'sec',
                'filing_type': filing['filing_type'],
                'filing_date': filing['filing_date'],
                'fiscal_year': filing['fiscal_year'],
                'fiscal_quarter': filing.get('fiscal_quarter'),
                'accession_number': filing['accession_number'],
                'section': test_section['section_code'],
                'section_name': test_section['section_name'],
                'chunk_index': i,
                'chunk_text': chunk_text,
                'chunk_tokens': chunk_tokens,
                'has_tables': len(tables) > 0,
                'gcs_path': gcs_path
            })
        
        # Upload to Qdrant
        qdrant.upload_vectors(
            collection_name=collection_name,
            vectors=embeddings,
            payloads=payloads
        )
        
        print(f"✅ Uploaded {len(embeddings)} vectors to Qdrant")
        print()
        
        # ============================================================
        # STEP 9: Test Semantic Search
        # ============================================================
        print("🔎 Step 9: Testing semantic search...")
        
        # Test query
        query = "What are Apple's main business segments and revenue sources?"
        query_embedding = embedder.embed_query(query)
        
        # Search Qdrant
        from qdrant_client.http import models
        
        results = qdrant.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            limit=3,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key='ticker',
                        match=models.MatchValue(value=ticker)
                    )
                ]
            )
        )
        
        print(f"✅ Query: \"{query}\"")
        print(f"   Found {len(results)} results:")
        print()
        
        for i, result in enumerate(results):
            print(f"   Result {i+1} (score: {result['score']:.4f}):")
            print(f"   Section: {result['payload']['section']} - {result['payload']['section_name']}")
            print(f"   Chunk {result['payload']['chunk_index']}: {result['payload']['chunk_text'][:150]}...")
            print()
        
        # ============================================================
        # STEP 10: Mark Filing as Processed
        # ============================================================
        print("✅ Step 10: Updating filing status...")
        
        state.mark_sec_filing_processed(
            accession_number=filing['accession_number'],
            status='completed'
        )
        
        print(f"✅ Filing marked as completed")
        print()
        
        # ============================================================
        # STEP 11: Get Statistics
        # ============================================================
        print("📊 Step 11: Pipeline statistics...")
        
        stats = state.get_stats()
        collection_info = qdrant.get_collection_info(collection_name)
        
        print(f"PostgreSQL:")
        print(f"   SEC Filings: {stats['sec_filings'].get('total', 0)} total")
        print(f"   Completed: {stats['sec_filings'].get('completed', 0)}")
        print()
        print(f"Qdrant:")
        print(f"   Collection: {collection_name}")
        print(f"   Vectors: {collection_info.get('vectors_count', 0):,}")
        print()
        print(f"GCS:")
        print(f"   Bucket: {os.getenv('GCP_BUCKET_NAME')}")
        print(f"   Latest upload: {gcs_path}")
        print()
        
        # ============================================================
        # SUCCESS!
        # ============================================================
        print("=" * 80)
        print("✅ END-TO-END TEST COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print()
        print("Summary:")
        print(f"  • Fetched: {filing['filing_type']} for {ticker}")
        print(f"  • Processed: 1 section ({len(chunks)} chunks, {len(tables)} tables)")
        print(f"  • Generated: {len(embeddings)} embeddings (1024d)")
        print(f"  • Uploaded: Raw data to GCS")
        print(f"  • Uploaded: Vectors to Qdrant")
        print(f"  • Tracked: State in PostgreSQL")
        print(f"  • Tested: Semantic search retrieval")
        print()
        print("🎉 Full production pipeline is operational!")
        
    except Exception as e:
        logger.error(f"Pipeline test failed: {e}", exc_info=True)
        print(f"\n❌ Pipeline test failed: {e}")
        return 1
    
    finally:
        # Cleanup
        if 'db' in locals():
            db.close()
    
    return 0


if __name__ == "__main__":
    exit(main())
