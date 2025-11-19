# src/storage/vector_store_manager.py
"""Manager for Qdrant vector database operations"""

from typing import Dict, List, Optional, Any, Tuple
import uuid
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    Range,
    SearchRequest
)
from qdrant_client.http import models

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.config import config
from src.utils.logging_config import get_logger
from src.utils.retry_handler import retry_on_failure

logger = get_logger(__name__)


class VectorStoreManager:
    """Manages Qdrant vector database operations"""
    
    def __init__(self):
        """Initialize vector store manager"""
        self.client = QdrantClient(
            host=config.database.qdrant_host,
            port=config.database.qdrant_port
        )
        self.collection_name = config.database.qdrant_collection
        
        # Verify collection exists (with version compatibility handling)
        try:
            self.client.get_collection(self.collection_name)
            logger.info(f"Connected to Qdrant collection: {self.collection_name}")
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check if it's a version mismatch (collection exists but can't parse response)
            if "validation" in error_msg or "parsing" in error_msg:
                logger.warning(
                    f"Version mismatch detected with Qdrant server. "
                    f"Collection is usable despite warning."
                )
                
                # Verify collection exists with simpler check
                try:
                    collections = self.client.get_collections()
                    collection_names = [c.name for c in collections.collections]
                    
                    if self.collection_name in collection_names:
                        logger.info(f"✅ Verified collection exists: {self.collection_name}")
                    else:
                        raise ValueError(f"Collection {self.collection_name} not found")
                except ValueError:
                    raise
                except Exception as verify_error:
                    logger.error(f"Could not verify collection: {verify_error}")
                    raise
            else:
                # Different error - collection actually doesn't exist
                logger.error(f"Collection {self.collection_name} not found: {e}")
                raise
    
    # ==================== UPSERT OPERATIONS ====================
    
    @retry_on_failure
    def upsert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> int:
        """
        Upsert chunks into vector database
        
        Args:
            chunks: List of chunk dictionaries with keys:
                - chunk_id: Unique identifier
                - embedding: Vector embedding
                - text: Original text
                - metadata: Dict with ticker, source_type, etc.
            batch_size: Number of chunks to upsert at once
            
        Returns:
            Number of chunks upserted
        """
        if not chunks:
            logger.warning("No chunks to upsert")
            return 0
        
        total_upserted = 0
        
        # Process in batches
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            points = []
            
            for chunk in batch:
                # Create point struct
                point = PointStruct(
                    id=str(uuid.uuid4()),  # Generate unique ID
                    vector=chunk['embedding'],
                    payload={
                        "chunk_id": chunk['chunk_id'],
                        "text": chunk['text'],
                        **chunk.get('metadata', {})
                    }
                )
                points.append(point)
            
            # Upsert batch
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            total_upserted += len(points)
            logger.info(f"Upserted batch {i//batch_size + 1}: {len(points)} chunks")
        
        logger.info(f"✅ Total upserted: {total_upserted} chunks")
        return total_upserted
    
    def upsert_single_chunk(
        self,
        chunk_id: str,
        embedding: List[float],
        text: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Upsert a single chunk
        
        Args:
            chunk_id: Unique chunk identifier
            embedding: Vector embedding
            text: Original text
            metadata: Metadata dict
            
        Returns:
            Point ID
        """
        point_id = str(uuid.uuid4())
        
        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload={
                "chunk_id": chunk_id,
                "text": text,
                **metadata
            }
        )
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )
        
        logger.debug(f"Upserted chunk: {chunk_id}")
        return point_id
    
    # ==================== SEARCH OPERATIONS ====================
    
    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors
        
        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filters: Optional filters dict with keys like:
                - ticker: str or List[str]
                - source_type: str (sec_filing, wikipedia, news)
                - filing_type: str (10-K, 10-Q)
                - section: str
                
        Returns:
            List of matching chunks with scores
        """
        # Build filter
        query_filter = self._build_filter(filters) if filters else None
        
        # Perform search
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
            with_payload=True,
            with_vectors=False
        )
        
        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.id,
                "score": result.score,
                "chunk_id": result.payload.get("chunk_id"),
                "text": result.payload.get("text"),
                "metadata": {
                    k: v for k, v in result.payload.items()
                    if k not in ["chunk_id", "text"]
                }
            })
        
        logger.info(f"Search returned {len(formatted_results)} results")
        return formatted_results
    
    def search_by_ticker(
        self,
        query_vector: List[float],
        ticker: str,
        limit: int = 10,
        source_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search within a specific company's documents
        
        Args:
            query_vector: Query embedding
            ticker: Company ticker symbol
            limit: Maximum results
            source_type: Optional filter by source (sec_filing, wikipedia, news)
            
        Returns:
            List of matching chunks
        """
        filters = {"ticker": ticker}
        if source_type:
            filters["source_type"] = source_type
        
        return self.search(query_vector, limit=limit, filters=filters)
    
    def search_filings(
        self,
        query_vector: List[float],
        ticker: Optional[str] = None,
        filing_type: Optional[str] = None,
        section: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search within SEC filings
        
        Args:
            query_vector: Query embedding
            ticker: Optional company filter
            filing_type: Optional filing type (10-K, 10-Q)
            section: Optional section filter
            limit: Maximum results
            
        Returns:
            List of matching chunks
        """
        filters = {"source_type": "sec_filing"}
        if ticker:
            filters["ticker"] = ticker
        if filing_type:
            filters["filing_type"] = filing_type
        if section:
            filters["section"] = section
        
        return self.search(query_vector, limit=limit, filters=filters)
    
    # ==================== DELETE OPERATIONS ====================
    
    def delete_by_chunk_ids(self, chunk_ids: List[str]) -> int:
        """
        Delete chunks by their chunk_ids
        
        Args:
            chunk_ids: List of chunk IDs to delete
            
        Returns:
            Number of chunks deleted
        """
        if not chunk_ids:
            return 0
        
        # Build filter for chunk_ids
        filter_condition = Filter(
            must=[
                FieldCondition(
                    key="chunk_id",
                    match=MatchAny(any=chunk_ids)
                )
            ]
        )
        
        # Delete points matching filter
        result = self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=filter_condition
            )
        )
        
        logger.info(f"Deleted {len(chunk_ids)} chunks by chunk_id")
        return len(chunk_ids)
    
    def delete_by_ticker(self, ticker: str, source_type: Optional[str] = None) -> int:
        """
        Delete all chunks for a company
        
        Args:
            ticker: Company ticker
            source_type: Optional filter by source type
            
        Returns:
            Estimated number of chunks deleted
        """
        conditions = [
            FieldCondition(
                key="ticker",
                match=MatchValue(value=ticker)
            )
        ]
        
        if source_type:
            conditions.append(
                FieldCondition(
                    key="source_type",
                    match=MatchValue(value=source_type)
                )
            )
        
        filter_condition = Filter(must=conditions)
        
        # Count before deletion
        count_result = self.client.count(
            collection_name=self.collection_name,
            count_filter=filter_condition
        )
        count = count_result.count
        
        # Delete
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=filter_condition
            )
        )
        
        logger.info(f"Deleted ~{count} chunks for ticker {ticker}")
        return count
    
    def delete_expired_news(self) -> int:
        """
        Delete news chunks that are past their retention period
        This should be coordinated with metadata_store_manager
        
        Returns:
            Number of chunks deleted
        """
        logger.info("Delete expired news - coordinate with metadata store")
        return 0
    
    # ==================== UTILITY METHODS ====================
    
    def _build_filter(self, filters: Dict[str, Any]) -> Filter:
        """
        Build Qdrant filter from dict
        
        Args:
            filters: Dict with filter conditions
            
        Returns:
            Qdrant Filter object
        """
        conditions = []
        
        for key, value in filters.items():
            if isinstance(value, list):
                # Multiple values (OR condition)
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchAny(any=value)
                    )
                )
            else:
                # Single value
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
        
        return Filter(must=conditions)
    
    def count_chunks(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Count chunks matching filters
        
        Args:
            filters: Optional filter dict
            
        Returns:
            Number of matching chunks
        """
        query_filter = self._build_filter(filters) if filters else None
        
        result = self.client.count(
            collection_name=self.collection_name,
            count_filter=query_filter
        )
        
        return result.count
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        Get collection statistics (with version compatibility)
        
        Returns:
            Collection info dict
        """
        try:
            collection = self.client.get_collection(self.collection_name)
            
            return {
                "name": self.collection_name,
                "vectors_count": collection.points_count,
                "indexed_vectors_count": collection.indexed_vectors_count,
                "status": collection.status,
                "vector_size": collection.config.params.vectors.size,
            }
        except:
            # Fallback if version mismatch
            logger.warning("Could not get full collection info (version mismatch)")
            return {
                "name": self.collection_name,
                "vectors_count": 0,
                "indexed_vectors_count": 0,
                "status": "unknown",
                "vector_size": 768,
            }
    
    def scroll_chunks(
        self,
        limit: int = 100,
        offset: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Scroll through chunks (for batch processing)
        
        Args:
            limit: Number of chunks to retrieve
            offset: Offset ID for pagination
            filters: Optional filters
            
        Returns:
            Tuple of (chunks, next_offset)
        """
        query_filter = self._build_filter(filters) if filters else None
        
        results, next_offset = self.client.scroll(
            collection_name=self.collection_name,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
            scroll_filter=query_filter
        )
        
        chunks = []
        for point in results:
            chunks.append({
                "id": point.id,
                "chunk_id": point.payload.get("chunk_id"),
                "text": point.payload.get("text"),
                "metadata": {
                    k: v for k, v in point.payload.items()
                    if k not in ["chunk_id", "text"]
                }
            })
        
        return chunks, next_offset