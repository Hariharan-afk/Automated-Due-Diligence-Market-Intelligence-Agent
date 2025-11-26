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
from qdrant_client import QdrantClient
from src.tools.gcp_client import get_gcp_client
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
        self.gcp_client = get_gcp_client()
        self.alpha = SEARCH_CONFIG["alpha"]
        
        # Load all chunks for BM25
        print("🔄 Building BM25 index...")
        self.chunks = self._load_all_chunks()
        self._build_bm25_index()
        print(f"✅ Indexed {len(self.chunks)} chunks")
    
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
    
    def search(self, query: str, top_k: int = 20) -> List[Dict]:
        """
        Hybrid search: alpha * semantic + (1-alpha) * keyword
        
        Args:
            query: Search query
            top_k: Number of results
        
        Returns:
            List of chunks with scores
        """
        # 1. Semantic search (Qdrant) - FIXED API call
        query_embedding = self.gcp_client.get_embedding(query)
        
        # Use query() method instead of search() in newer Qdrant versions
        try:
            vector_results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                limit=len(self.chunks)
            ).points
        except AttributeError:
            # Fallback to search() if query_points doesn't exist
            vector_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=len(self.chunks)
            )
        
        # Map to scores
        vector_scores = {}
        for result in vector_results:
            chunk_id = result.payload.get("chunk_id")
            score = result.score if hasattr(result, 'score') else 0.0
            vector_scores[chunk_id] = score
        
        # 2. BM25 search
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # 3. Combine scores
        combined_results = []
        for i, chunk in enumerate(self.chunks):
            chunk_id = chunk['chunk_id']
            
            v_score = vector_scores.get(chunk_id, 0.0)
            b_score = bm25_scores[i]
            
            # Normalize BM25
            max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1
            b_score_norm = b_score / max_bm25
            
            # Hybrid score
            combined_score = self.alpha * v_score + (1 - self.alpha) * b_score_norm
            
            combined_results.append({
                **chunk,
                "score": combined_score
            })
        
        # Sort and return top-k
        combined_results.sort(key=lambda x: x['score'], reverse=True)
        return combined_results[:top_k]