"""Create Qdrant collection for vector storage"""

import sys
from pathlib import Path
import os

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent  # DATA_PIPELINE directory
sys.path.insert(0, str(project_root))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def create_collection():
    """Create Qdrant collection with proper configuration"""
    
    print("\n" + "="*70)
    print("CREATING QDRANT COLLECTION")
    print("="*70 + "\n")
    
    # Connect to Qdrant
    client = QdrantClient(
        host=config.database.qdrant_host,
        port=config.database.qdrant_port
    )
    
    collection_name = config.database.qdrant_collection
    
    # Check if collection exists
    try:
        existing = client.get_collection(collection_name)
        print(f"⚠️  Collection '{collection_name}' already exists")
        print(f"   Vectors: {existing.points_count}")
        print(f"   Status: {existing.status}")
        
        response = input("\nDelete and recreate? (yes/no): ")
        if response.lower() == 'yes':
            client.delete_collection(collection_name)
            print(f"🗑️  Deleted existing collection")
        else:
            print("Keeping existing collection")
            return
    except:
        print(f"Creating new collection: {collection_name}")
    
    # Determine embedding dimension
    # all-mpnet-base-v2 = 768 dimensions
    embedding_model = config.pipeline.embedding_model
    
    dimension_map = {
        'all-mpnet-base-v2': 768,
        'all-MiniLM-L6-v2': 384,
        'all-MiniLM-L12-v2': 384
    }
    
    vector_size = dimension_map.get(embedding_model, 768)
    
    print(f"\nConfiguration:")
    print(f"  Collection: {collection_name}")
    print(f"  Embedding model: {embedding_model}")
    print(f"  Vector dimension: {vector_size}")
    print(f"  Distance metric: Cosine")
    
    # Create collection
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE
        )
    )
    
    print(f"\n✅ Collection created successfully!")
    
    # Create payload indexes for filtering
    print(f"\nCreating payload indexes...")
    
    # Index frequently filtered fields
    from qdrant_client.models import PayloadSchemaType
    
    indexes = [
        ('ticker', PayloadSchemaType.KEYWORD),
        ('filing_type', PayloadSchemaType.KEYWORD),
        ('section', PayloadSchemaType.KEYWORD),
        ('chunk_type', PayloadSchemaType.KEYWORD),
        ('contains_table', PayloadSchemaType.BOOL)
    ]
    
    for field_name, field_type in indexes:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_type
            )
            print(f"  ✅ Created index: {field_name}")
        except Exception as e:
            print(f"  ⚠️  Index {field_name}: {e}")
    
    # Verify
    collection_info = client.get_collection(collection_name)
    print(f"\n✅ Collection ready!")
    print(f"   Name: {collection_info.config.params.vectors.size}d vectors")
    print(f"   Status: {collection_info.status}")
    
    print(f"\n{'='*70}")
    print("SETUP COMPLETE")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    try:
        create_collection()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Make sure Docker is running:")
        print("   cd docker && docker-compose up -d")
        import traceback
        traceback.print_exc()