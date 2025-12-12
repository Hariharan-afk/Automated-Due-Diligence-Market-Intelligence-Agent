"""
Cleanup Script - Delete All Data from Cloud Storage

⚠️  WARNING: This script will DELETE ALL DATA from:
- Qdrant Cloud (all vectors in collection)
- Google Cloud Storage (all files in bucket)
- Supabase PostgreSQL (all tables data)

Usage:
    python scripts/cleanup_all_data.py
    
    # Or delete specific components:
    python scripts/cleanup_all_data.py --qdrant-only
    python scripts/cleanup_all_data.py --gcs-only
    python scripts/cleanup_all_data.py --postgres-only
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cloud import GCSConnector, PostgresConnector, QdrantConnector
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Load environment variables
load_dotenv()

COLLECTION_NAME = "company_data"


def cleanup_qdrant(qdrant: QdrantConnector, collection_name: str) -> bool:
    """Delete all vectors from Qdrant collection"""
    
    print("\n" + "=" * 80)
    print("🗑️  CLEANING UP QDRANT CLOUD")
    print("=" * 80 + "\n")
    
    try:
        # Get collection info
        info = qdrant.get_collection_info(collection_name)
        vector_count = info.get('vectors_count', 0)
        
        print(f"📊 Current state:")
        print(f"   Collection: {collection_name}")
        print(f"   Vectors: {vector_count:,}")
        print()
        
        if vector_count == 0:
            print("ℹ️  Collection is already empty")
            return True
        
        # Confirm deletion
        print(f"⚠️  WARNING: This will delete {vector_count:,} vectors!")
        response = input("   Type 'DELETE' to confirm: ")
        
        if response != 'DELETE':
            print("❌ Cancelled")
            return False
        
        # Delete the collection entirely and recreate it
        print(f"\n🔄 Deleting collection '{collection_name}'...")
        qdrant.client.delete_collection(collection_name=collection_name)
        
        print(f"🔄 Recreating empty collection...")
        qdrant.create_collection(
            collection_name=collection_name,
            vector_size=1024,
            distance='Cosine',
            recreate=True
        )
        
        print(f"✅ Qdrant cleanup complete!")
        return True
        
    except Exception as e:
        logger.error(f"Qdrant cleanup failed: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return False


def cleanup_gcs(gcs: GCSConnector, prefixes: list = None) -> bool:
    """Delete all files from GCS bucket"""
    
    print("\n" + "=" * 80)
    print("🗑️  CLEANING UP GOOGLE CLOUD STORAGE")
    print("=" * 80 + "\n")
    
    try:
        if prefixes is None:
            prefixes = ['raw/sec/', 'raw/wikipedia/', 'raw/news/']
        
        total_deleted = 0
        
        for prefix in prefixes:
            print(f"\n📂 Checking prefix: {prefix}")
            
            # List all files with this prefix
            files = gcs.list_files(prefix=prefix)
            
            if not files:
                print(f"   ℹ️  No files found")
                continue
            
            print(f"   Found {len(files)} file(s)")
            print(f"   ⚠️  WARNING: This will delete {len(files)} file(s)!")
            response = input("   Type 'DELETE' to confirm: ")
            
            if response != 'DELETE':
                print("   ❌ Cancelled")
                continue
            
            # Delete files
            deleted = 0
            for file_path in files:
                try:
                    gcs.delete_file(file_path)
                    deleted += 1
                    if deleted % 10 == 0:
                        print(f"   🔄 Deleted {deleted}/{len(files)}...")
                except Exception as e:
                    logger.warning(f"Failed to delete {file_path}: {e}")
            
            print(f"   ✅ Deleted {deleted} file(s)")
            total_deleted += deleted
        
        print(f"\n✅ GCS cleanup complete! Deleted {total_deleted} file(s) total")
        return True
        
    except Exception as e:
        logger.error(f"GCS cleanup failed: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return False


def cleanup_postgres(db: PostgresConnector) -> bool:
    """Delete all data from PostgreSQL tables"""
    
    print("\n" + "=" * 80)
    print("🗑️  CLEANING UP POSTGRESQL (SUPABASE)")
    print("=" * 80 + "\n")
    
    try:
        tables = [
            'sec_filings',
            'wikipedia_pages',
            'news_articles',
            'pipeline_runs'
        ]
        
        print(f"📊 Tables to clean:")
        for table in tables:
            print(f"   - {table}")
        print()
        
        # Get row counts
        total_rows = 0
        for table in tables:
            try:
                result = db.fetch_one(f"SELECT COUNT(*) as count FROM {table}")
                count = result['count'] if result else 0
                print(f"   {table}: {count} rows")
                total_rows += count
            except Exception as e:
                logger.warning(f"Could not count {table}: {e}")
                print(f"   {table}: (table might not exist)")
        
        print()
        
        if total_rows == 0:
            print("ℹ️  All tables are already empty")
            return True
        
        # Confirm deletion
        print(f"⚠️  WARNING: This will delete {total_rows} row(s) across all tables!")
        response = input("   Type 'DELETE' to confirm: ")
        
        if response != 'DELETE':
            print("❌ Cancelled")
            return False
        
        # Truncate tables
        print(f"\n🔄 Truncating tables...")
        for table in tables:
            try:
                db.execute(f"TRUNCATE TABLE {table} CASCADE")
                print(f"   ✅ Truncated {table}")
            except Exception as e:
                logger.warning(f"Could not truncate {table}: {e}")
                print(f"   ⚠️  {table} (might not exist)")
        
        print(f"\n✅ PostgreSQL cleanup complete!")
        return True
        
    except Exception as e:
        logger.error(f"PostgreSQL cleanup failed: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return False


def main():
    """Run cleanup script"""
    
    parser = argparse.ArgumentParser(description='Clean up all cloud storage data')
    parser.add_argument('--qdrant-only', action='store_true', help='Only clean Qdrant')
    parser.add_argument('--gcs-only', action='store_true', help='Only clean GCS')
    parser.add_argument('--postgres-only', action='store_true', help='Only clean PostgreSQL')
    parser.add_argument('--collection', default=COLLECTION_NAME, help='Qdrant collection name')
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("🧹 CLOUD STORAGE CLEANUP SCRIPT")
    print("=" * 80)
    print()
    print("⚠️  WARNING: This will DELETE data from cloud storage!")
    print()
    
    # Determine what to clean
    clean_all = not (args.qdrant_only or args.gcs_only or args.postgres_only)
    clean_qdrant = clean_all or args.qdrant_only
    clean_gcs = clean_all or args.gcs_only
    clean_postgres = clean_all or args.postgres_only
    
    print("📋 Targets:")
    if clean_qdrant:
        print("   ✓ Qdrant Cloud")
    if clean_gcs:
        print("   ✓ Google Cloud Storage")
    if clean_postgres:
        print("   ✓ PostgreSQL (Supabase)")
    print()
    
    # Final confirmation for cleaning all
    if clean_all:
        print("⚠️  You are about to clean ALL cloud storage!")
        response = input("   Type 'YES' to proceed: ")
        if response != 'YES':
            print("\n❌ Cancelled")
            return 1
    
    try:
        # Initialize connectors only for what we need
        qdrant = None
        gcs = None
        db = None
        
        if clean_qdrant:
            print("\n🔧 Connecting to Qdrant Cloud...")
            qdrant = QdrantConnector(
                url=os.getenv('QDRANT_URL'),
                api_key=os.getenv('QDRANT_API_KEY')
            )
        
        if clean_gcs:
            print("🔧 Connecting to Google Cloud Storage...")
            gcs = GCSConnector(
                bucket_name=os.getenv('GCP_BUCKET_NAME'),
                project_id=os.getenv('GCP_PROJECT_ID'),
                credentials_path=os.getenv('GCP_CREDENTIALS_PATH')
            )
        
        if clean_postgres:
            print("🔧 Connecting to PostgreSQL...")
            db = PostgresConnector(
                host=os.getenv('POSTGRES_HOST'),
                port=int(os.getenv('POSTGRES_PORT')),
                database=os.getenv('POSTGRES_DB'),
                user=os.getenv('POSTGRES_USER'),
                password=os.getenv('POSTGRES_PASSWORD')
            )
        
        print("✅ All connections established\n")
        
        # Run cleanup operations
        results = []
        
        if clean_qdrant and qdrant:
            results.append(("Qdrant", cleanup_qdrant(qdrant, args.collection)))
        
        if clean_gcs and gcs:
            results.append(("GCS", cleanup_gcs(gcs)))
        
        if clean_postgres and db:
            results.append(("PostgreSQL", cleanup_postgres(db)))
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 CLEANUP SUMMARY")
        print("=" * 80 + "\n")
        
        for name, success in results:
            status = "✅ Success" if success else "❌ Failed"
            print(f"   {name}: {status}")
        
        print()
        
        all_success = all(success for _, success in results)
        if all_success:
            print("🎉 All cleanup operations completed successfully!")
            return 0
        else:
            print("⚠️  Some cleanup operations failed. Check logs for details.")
            return 1
        
    except Exception as e:
        logger.error(f"Cleanup script failed: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        return 1
    
    finally:
        # Close connections
        if db:
            db.close()


if __name__ == "__main__":
    exit(main())
