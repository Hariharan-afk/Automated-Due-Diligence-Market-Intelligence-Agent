"""
Test infrastructure connections

Run this script after setting up cloud infrastructure to verify all connections.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cloud import GCSConnector, PostgresConnector, QdrantConnector
from src.embedding import Embedder

# Load environment variables
load_dotenv()

print("="*70)
print("INFRASTRUCTURE CONNECTION TEST")
print("="*70)

# Test 1: GCS
print("\n1. Testing Google Cloud Storage...")
try:
    gcs = GCSConnector(
        bucket_name=os.getenv('GCP_BUCKET_NAME'),
        project_id=os.getenv('GCP_PROJECT_ID'),
        credentials_path=os.getenv('GCP_CREDENTIALS_PATH')
    )
    
    # Try to upload test file
    test_data = {"test": "connection", "timestamp": "2024-12-09"}
    gcs.upload_data(test_data, 'test/connection_test.json')
    
    # Try to download
    downloaded = gcs.download_data('test/connection_test.json')
    
    if downloaded == test_data:
        print("✅ GCS: Connected and working!")
        print(f"   Bucket: gs://{os.getenv('GCP_BUCKET_NAME')}")
    else:
        print("❌ GCS: Upload/download mismatch")
        
except Exception as e:
    print(f"❌ GCS: Failed - {e}")

# Test 2: PostgreSQL
print("\n2. Testing PostgreSQL...")
try:
    db = PostgresConnector(
        host=os.getenv('POSTGRES_HOST'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD')
    )
    
    # Create tables
    print("   Creating database schema...")
    db.create_tables()
    
    # Test query
    result = db.fetch_one("SELECT 1 as test")
    
    if result and result['test'] == 1:
        print("✅ PostgreSQL: Connected and tables created!")
        print(f"   Host: {os.getenv('POSTGRES_HOST')}")
        print("   Tables: sec_filings, wikipedia_pages, news_articles, pipeline_runs")
    else:
        print("❌ PostgreSQL: Query failed")
        
    db.close()
    
except Exception as e:
    print(f"❌ PostgreSQL: Failed - {e}")
    print("   Check your credentials in .env file")

# Test 3: Qdrant
print("\n3. Testing Qdrant Cloud...")
try:
    qdrant = QdrantConnector(
        url=os.getenv('QDRANT_URL'),
        api_key=os.getenv('QDRANT_API_KEY')
    )
    
    # Create test collection
    print("   Creating test collection...")
    qdrant.create_collection(
        collection_name='test_collection',
        vector_size=1024,
        distance='Cosine',
        recreate=True  # Recreate if exists
    )
    
    # Get info
    info = qdrant.get_collection_info('test_collection')
    
    if info and info['name'] == 'test_collection':
        print("✅ Qdrant: Connected and collection created!")
        print(f"   URL: {os.getenv('QDRANT_URL')}")
        print(f"   Collection: test_collection (1024d, Cosine)")
    else:
        print("❌ Qdrant: Collection creation failed")
        
except Exception as e:
    print(f"❌ Qdrant: Failed - {e}")
    print("   Check your URL and API key in .env file")

# Test 4: Embedder
print("\n4. Testing Embedder (BGE-large-en-v1.5)...")
try:
    embedder = Embedder()
    
    # Test embedding
    test_embedding = embedder.embed("Test query for infrastructure verification")
    
    if test_embedding.shape == (1024,):
        print("✅ Embedder: Working!")
        print(f"   Model: {embedder.model_name}")
        print(f"   Dimension: {embedder.dimension}d")
        print(f"   Device: {embedder.device}")
    else:
        print(f"❌ Embedder: Wrong dimension - {test_embedding.shape}")
        
except Exception as e:
    print(f"❌ Embedder: Failed - {e}")

print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70)
print("\nNext steps:")
print("  1. If all tests passed ✅ - Infrastructure is ready!")
print("  2. If any test failed ❌ - Check the setup guide and credentials")
print("  3. Ready to proceed with Phase 4 (fetcher updates)")
