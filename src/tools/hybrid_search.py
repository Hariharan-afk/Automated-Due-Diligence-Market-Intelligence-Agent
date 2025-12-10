"""
tools/hybrid_search.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Hybrid Search: Qdrant (semantic) + BM25 (keyword)
FIXED for latest Qdrant client API
"""

import sys
sys.path.append('.')

from typing import List, Dict
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models
from src.tools.local_client import get_local_client
from src.config import QDRANT_CONFIG, EMBEDDING_CONFIG, SEARCH_CONFIG
from rank_bm25 import BM25Okapi

class HybridSearchEngine:
    """Combines semantic (Qdrant) + keyword (BM25) search"""
    
    def __init__(self):
        if not QDRANT_CONFIG["url"] or not QDRANT_CONFIG["api_key"]:
            raise ValueError("❌ QDRANT_URL and QDRANT_API_KEY must be set in environment variables.")
            
        print(f"🔌 Connecting to Qdrant Cloud: {QDRANT_CONFIG['url']}")
        self.client = QdrantClient(
            url=QDRANT_CONFIG["url"],
            api_key=QDRANT_CONFIG["api_key"]
        )
        self.collection_name = QDRANT_CONFIG["collection_name"]
        self.local_client = get_local_client()
        self.alpha = SEARCH_CONFIG["alpha"]
        
        # Load all chunks for BM25
        print("🔄 Building BM25 index...")
        self.chunks = self._load_all_chunks()
        self._build_bm25_index()
        print(f"✅ Indexed {len(self.chunks)} chunks")
        if self.chunks:
            print(f"🔍 DEBUG: First chunk metadata: {self.chunks[0]['metadata']}")
    
    def _load_all_chunks(self) -> List[Dict]:
        """Load all chunks from Qdrant for BM25"""
        chunks = []
        offset = None
        
        while True:
            results, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            for point in results:
                chunks.append({
                    "id": point.id,
                    "chunk_id": point.payload.get("chunk_id"),
                    "raw_chunk": point.payload.get("raw_chunk"),
                    "metadata": {k: v for k, v in point.payload.items() 
                                if k not in ["chunk_id", "raw_chunk"]}
                })
            
            if offset is None:
                break
        
        return chunks
    
    def _build_bm25_index(self):
        """Build BM25 index"""
        tokenized = [chunk['raw_chunk'].lower().split() for chunk in self.chunks]
        self.bm25 = BM25Okapi(tokenized)
    
    def search(self, query: str, top_k: int = 20, source_filter: str = None) -> List[Dict]:
        """
        Hybrid search: alpha * semantic + (1-alpha) * keyword
        
        Args:
            query: Search query
            top_k: Number of results
            source_filter: Optional source type to filter by (e.g., 'sec', 'news', 'wikipedia')
        
        Returns:
            List of chunks with scores
        """
        # 1. Semantic search (Qdrant)
        query_embedding = self.local_client.get_embedding(query)
        
        # Create Qdrant filter if source_filter is provided
        qdrant_filter = None
        if source_filter:
            qdrant_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="data_source_type",
                        match=models.MatchValue(value=source_filter)
                    )
                ]
            )
        
        # Use query() method instead of search() in newer Qdrant versions
        try:
            vector_results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                query_filter=qdrant_filter,
                limit=len(self.chunks) # Get many to rerank
            ).points
        except AttributeError:
            # Fallback to search() if query_points doesn't exist
            vector_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=qdrant_filter,
                limit=len(self.chunks)
            )
        
        # Map vector scores
        sem_scores = {point.id: point.score for point in vector_results}
        
        # 2. Keyword search (BM25)
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # Normalize scores
        def normalize(scores):
            if len(scores) == 0: return []
            min_s, max_s = min(scores), max(scores)
            if max_s == min_s: return [0.5] * len(scores)
            return [(s - min_s) / (max_s - min_s) for s in scores]
            
        # 3. Combine scores
        combined_results = []
        
        # Get normalized BM25 scores for filtered chunks
        # Note: self.bm25.get_scores returns scores for ALL chunks in index order
        # We only care about the ones that match our filter
        
        # Create a map of chunk_id -> combined_score
        # We need to iterate through ALL chunks to match BM25 indices
        
        all_bm25_norm = normalize(bm25_scores)
        
        # Get max semantic score for normalization (approximate)
        max_sem = max(sem_scores.values()) if sem_scores else 1.0
        
        for i, chunk in enumerate(self.chunks):
            # Apply filter
            if source_filter and chunk['metadata'].get('data_source_type') != source_filter:
                continue
                
            # Get semantic score (default 0 if not in vector results)
            # Note: Qdrant uses UUIDs or ints for IDs. 
            # We need to match Qdrant ID with our chunk ID
            # In _load_all_chunks we stored point.id as "id"
            
            sem_score = sem_scores.get(chunk['id'], 0.0)
            # Normalize sem_score roughly
            sem_score_norm = sem_score / max_sem if max_sem > 0 else 0
            
            kw_score_norm = all_bm25_norm[i]
            
            final_score = (self.alpha * sem_score_norm) + ((1 - self.alpha) * kw_score_norm)
            
            combined_results.append({
                **chunk,
                "final_score": final_score
            })
            
        # Sort by final score
        combined_results.sort(key=lambda x: x['final_score'], reverse=True)
        
        return combined_results[:top_k]