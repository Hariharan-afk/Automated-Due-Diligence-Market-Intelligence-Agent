"""Create Qdrant collection for vector storage (non-interactive)"""

import sys
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
sys.path.insert(0, str(project_root))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def create_collection(force_recreate=False):
    """Create Qdrant collection with proper configuration (non-interactive)"""
    
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
        
        if force_recreate:
            client.delete_collection(collection_name)
            print(f"🗑️  Deleted existing collection")
        else:
            print("✅ Collection already exists - keeping it")
            return True
    except Exception as e:
        print(f"Creating new collection: {collection_name}")
    
    # Determine embedding dimension
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
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Create Qdrant collection')
    parser.add_argument('--force', action='store_true', help='Force recreate if exists')
    args = parser.parse_args()
    
    try:
        create_collection(force_recreate=args.force)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Make sure Docker is running:")
        print("   cd docker && docker-compose up -d")
        import traceback
        traceback.print_exc()
        sys.exit(1)

