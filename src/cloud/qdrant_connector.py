"""
Qdrant Connector

Handles vector database operations for RAG retrieval
"""

from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Any, Optional
import numpy as np
from pathlib import Path
from uuid import uuid4

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class QdrantConnector:
    """
    Qdrant connector for vector database operations
    
    Features:
    - Collection management
    - Vector upload with metadata
    - Semantic search with filters
    - Metadata updates
    - Vector deletion
    """
    
    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = 6333,
        prefer_grpc: bool = False
    ):
        """
        Initialize Qdrant connector
        
        Args:
            url: Qdrant Cloud URL (e.g., 'https://xyz.cloud.qdrant.io')
            api_key: Qdrant Cloud API key
            host: Self-hosted Qdrant host (if not using cloud)
            port: Self-hosted Qdrant port
            prefer_grpc: Use gRPC instead of HTTP
        """
        # Connect based on configuration
        if url and api_key:
            # Qdrant Cloud
            self.client = QdrantClient(url=url, api_key=api_key, prefer_grpc=prefer_grpc)
            logger.info(f"Connected to Qdrant Cloud: {url}")
        elif host:
            # Self-hosted
            self.client = QdrantClient(host=host, port=port, prefer_grpc=prefer_grpc)
            logger.info(f"Connected to Qdrant: {host}:{port}")
        else:
            # Local in-memory (for testing)
            self.client = QdrantClient(":memory:")
            logger.warning("Using in-memory Qdrant (data will be lost on restart)")
    
    def create_collection(
        self,
        collection_name: str,
        vector_size: int = 1024,
        distance: str = 'Cosine',
        recreate: bool = False
    ) -> bool:
        """
        Create a vector collection
        
        Args:
            collection_name: Name of collection
            vector_size: Dimension of vectors (1024 for BGE-large)
            distance: Distance metric ('Cosine', 'Euclid', 'Dot')
            recreate: If True, delete existing and recreate
        
        Returns:
            True if successful
        """
        try:
            # Check if exists
            collections = self.client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)
            
            if exists and recreate:
                logger.info(f"Deleting existing collection: {collection_name}")
                self.client.delete_collection(collection_name)
                exists = False
            
            if not exists:
                # Map distance string to enum
                distance_map = {
                    'Cosine': models.Distance.COSINE,
                    'Euclid': models.Distance.EUCLID,
                    'Dot': models.Distance.DOT
                }
                
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=vector_size,
                        distance=distance_map.get(distance, models.Distance.COSINE)
                    )
                )
                logger.info(f"Created collection: {collection_name} (size={vector_size}, distance={distance})")
                
                # Create payload indexes for fast filtering
                self._create_indexes(collection_name)
            else:
                logger.info(f"Collection already exists: {collection_name}")
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            return False
    
    def _create_indexes(self, collection_name: str):
        """Create payload indexes for filtering"""
        index_fields = [
            ('ticker', models.PayloadSchemaType.KEYWORD),
            ('data_source', models.PayloadSchemaType.KEYWORD),
            ('filing_type', models.PayloadSchemaType.KEYWORD),
            ('fiscal_year', models.PayloadSchemaType.INTEGER),
            ('section', models.PayloadSchemaType.KEYWORD),
            ('has_tables', models.PayloadSchemaType.BOOL),
            ('expires_at', models.PayloadSchemaType.DATETIME),
        ]
        
        for field_name, schema_type in index_fields:
            try:
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=schema_type
                )
                logger.debug(f"Created index on field: {field_name}")
            except Exception as e:
                # Index might already exist
                logger.debug(f"Index creation for {field_name}: {e}")
    
    def upload_vectors(
        self,
        collection_name: str,
        vectors: np.ndarray,
        payloads: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ) -> bool:
        """
        Upload vectors with metadata
        
        Args:
            collection_name: Target collection
            vectors: Array of shape (n, dimension)
            payloads: List of metadata dicts (one per vector)
            ids: Optional list of IDs (auto-generated if None)
        
        Returns:
            True if successful
        """
        try:
            n_vectors = len(vectors)
            
            # Generate IDs if not provided
            if ids is None:
                ids = [str(uuid4()) for _ in range(n_vectors)]
            
            # Validate
            if len(payloads) != n_vectors:
                raise ValueError(f"Payloads ({len(payloads)}) != vectors ({n_vectors})")
            
            if len(ids) != n_vectors:
                raise ValueError(f"IDs ({len(ids)}) != vectors ({n_vectors})")
            
            # Create points
            points = []
            for i in range(n_vectors):
                points.append(models.PointStruct(
                    id=ids[i],
                    vector=vectors[i].tolist(),
                    payload=payloads[i]
                ))
            
            # Upload in batches
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i:i+batch_size]
                self.client.upsert(
                    collection_name=collection_name,
                    points=batch
                )
                logger.debug(f"Uploaded batch {i//batch_size + 1}: {len(batch)} vectors")
            
            logger.info(f"Uploaded {n_vectors} vectors to {collection_name}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to upload vectors: {e}")
            return False
    
    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        limit: int = 10,
        query_filter: Optional[models.Filter] = None,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors
        
        Args:
            collection_name: Collection to search
            query_vector: Query vector
            limit: Number of results
            query_filter: Optional filter on metadata
            score_threshold: Minimum similarity score
        
        Returns:
            List of result dicts with 'id', 'score', and 'payload'
        """
        try:
            results = self.client.search_points(
                collection_name=collection_name,
                query=query_vector.tolist(),
                query_filter=query_filter,
                limit=limit,
                score_threshold=score_threshold
            )
            
            # Convert to dict format
            output = []
            for hit in results:
                output.append({
                    'id': hit.id,
                    'score': hit.score,
                    'payload': hit.payload
                })
            
            logger.debug(f"Search returned {len(output)} results")
            return output
        
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def delete_vectors(
        self,
        collection_name: str,
        filters: Optional[models.Filter] = None,
        ids: Optional[List[str]] = None
    ) -> bool:
        """
        Delete vectors by filter or IDs
        
        Args:
            collection_name: Target collection
            filters: Delete vectors matching filter
            ids: Delete specific IDs
        
        Returns:
            True if successful
        """
        try:
            from qdrant_client.models import FilterSelector, PointIdsList
            
            if filters:
                # Delete by filter
                self.client.delete(
                    collection_name=collection_name,
                    points_selector=models.FilterSelector(filter=filters)
                )
                logger.info(f"Deleted vectors matching filter from {collection_name}")
            elif ids:
                # Delete by IDs
                self.client.delete(
                    collection_name=collection_name,
                    points_selector=models.PointIdsList(points=ids)
                )
                logger.info(f"Deleted {len(ids)} vectors from {collection_name}")
            else:
                logger.warning("No filters or IDs provided for deletion")
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False
    
    def update_payload(
        self,
        collection_name: str,
        payload: Dict[str, Any],
        filters: Optional[models.Filter] = None,
        ids: Optional[List[str]] = None
    ) -> bool:
        """
        Update payload for vectors
        
        Args:
            collection_name: Target collection
            payload: New payload data (will be merged with existing)
            filters: Update vectors matching filter
            ids: Update specific IDs
        
        Returns:
            True if successful
        """
        try:
            # Use models for selectors
            
            if filters:
                selector = models.FilterSelector(filter=filters)
            elif ids:
                selector = models.PointIdsList(points=ids)
            else:
                logger.warning("No filters or IDs provided for update")
                return False
            
            self.client.set_payload(
                collection_name=collection_name,
                payload=payload,
                points=selector
            )
            logger.info(f"Updated payload in {collection_name}")
            return True
        
        except Exception as e:
            logger.error(f"Payload update failed: {e}")
            return False
    
    def get_collection_info(self, collection_name: str) -> Optional[Dict]:
        """Get collection information"""
        try:
            info = self.client.get_collection(collection_name)
            return {
                'name': collection_name,
                'vectors_count': info.points_count,
                'indexed_vectors_count': info.indexed_vectors_count,
                'status': info.status
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return None


if __name__ == "__main__":
    # Example usage
    print("Testing QdrantConnector...")
    
    # Test with in-memory Qdrant
    connector = QdrantConnector()
    
    # Create collection
    connector.create_collection(
        collection_name='test_collection',
        vector_size=1024,
        distance='Cosine'
    )
    
    # Create test vectors
    vectors = np.random.rand(5, 1024).astype(np.float32)
    payloads = [
        {'ticker': 'AAPL', 'data_source': 'sec', 'text': f'Test chunk {i}'}
        for i in range(5)
    ]
    
    # Upload
    connector.upload_vectors('test_collection', vectors, payloads)
    
    # Search
    query_vector = np.random.rand(1024).astype(np.float32)
    results = connector.search('test_collection', query_vector, limit=3)
    
    print(f"\n✅ QdrantConnector test complete!")
    print(f"Uploaded 5 vectors, searched and got {len(results)} results")
    print(f"Collection info: {connector.get_collection_info('test_collection')}")
