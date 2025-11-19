# src/agents/researcher_agent.py
"""
Researcher Agent: Hybrid RAG (Semantic + BM25)
Pure retrieval - NO LLM involved
"""
import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np
from rank_bm25 import BM25Okapi
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Container for search results"""
    chunk_id: str
    content: str
    metadata: Dict[str, Any]
    semantic_score: float
    bm25_score: float
    hybrid_score: float
    rank: int
    
    def __repr__(self):
        return (f"SearchResult(rank={self.rank}, "
                f"hybrid={self.hybrid_score:.3f}, "
                f"sem={self.semantic_score:.3f}, "
                f"bm25={self.bm25_score:.3f})")


class ResearcherAgent:
    """
    Hybrid Retrieval Agent
    
    Formula: hybrid_score = α × semantic_score + (1-α) × bm25_score
    
    Where:
    - α ∈ [0,1]: Weight for semantic vs keyword search
    - semantic_score: Cosine similarity from Qdrant (0-1)
    - bm25_score: Keyword relevance (normalized 0-1)
    """
    
    def __init__(
        self,
        qdrant_host: str = None,
        qdrant_port: int = 6333,
        collection_name: str = "due_diligence_kb",
        embedding_model: str = "sentence-transformers/all-mpnet-base-v2",  # 768-dim model
        alpha: float = 0.5,
        top_k: int = 5
    ):
        """
        Initialize Researcher Agent
        
        Args:
            qdrant_host: Qdrant server (default: localhost)
            qdrant_port: Qdrant port (default: 6333)
            collection_name: Vector collection name
            embedding_model: Sentence transformer model
            alpha: Hybrid weight (0=BM25, 0.5=balanced, 1=semantic)
            top_k: Number of results to return
        """
        self.qdrant_host = qdrant_host or os.getenv('QDRANT_HOST', 'localhost')
        self.qdrant_port = qdrant_port
        self.collection_name = collection_name
        self.alpha = alpha
        self.top_k = top_k
        
        # Initialize Qdrant client
        logger.info(f"Connecting to Qdrant at {self.qdrant_host}:{self.qdrant_port}")
        self.qdrant_client = QdrantClient(
            host=self.qdrant_host,
            port=self.qdrant_port
        )
        
        # Verify collection exists (with version-compatible check)
        try:
            # Try to get collection info
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            logger.info(f"✓ Collection '{self.collection_name}' found "
                       f"({collection_info.points_count} points)")
        except Exception as e:
            # Fallback: Just check if collection exists with raw API
            logger.warning(f"⚠ Could not parse collection info (version mismatch): {e}")
            try:
                import requests
                response = requests.get(
                    f"http://{self.qdrant_host}:{self.qdrant_port}/collections/{self.collection_name}"
                )
                if response.status_code == 200:
                    data = response.json()
                    points_count = data.get('result', {}).get('points_count', '?')
                    logger.info(f"✓ Collection '{self.collection_name}' verified (fallback method, {points_count} points)")
                else:
                    raise Exception(f"Collection not found: HTTP {response.status_code}")
            except Exception as e2:
                logger.error(f"✗ Collection '{self.collection_name}' not accessible: {e2}")
                raise
        
        # Initialize embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # BM25 index (built on demand)
        self.bm25_index = None
        self.corpus_chunks = []
        self.chunk_map = {}
        self._bm25_loaded = False
        
        logger.info(f"✓ ResearcherAgent initialized (α={alpha}, top_k={top_k})")
    
    def load_corpus(self, ticker: str = None, limit: int = 10000):
        """
        Load corpus from Qdrant to build BM25 index
        
        Args:
            ticker: Filter by company ticker (optional)
            limit: Max chunks to load
        """
        if self._bm25_loaded:
            logger.info("BM25 index already loaded")
            return
        
        logger.info(f"Loading corpus from Qdrant (ticker={ticker or 'ALL'})...")
        
        chunks = []
        offset = None
        
        # Scroll through all points
        while len(chunks) < limit:
            result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            points, next_offset = result
            
            if not points:
                break
            
            for point in points:
                payload = point.payload
                
                # Filter by ticker if specified
                if ticker and payload.get('ticker') != ticker:
                    continue
                
                chunk = {
                    'chunk_id': str(point.id),
                    'content': payload.get('text', ''),
                    'metadata': payload
                }
                chunks.append(chunk)
                self.chunk_map[chunk['chunk_id']] = chunk
            
            offset = next_offset
            if offset is None:
                break
        
        logger.info(f"✓ Loaded {len(chunks)} chunks")
        
        # Build BM25 index
        if chunks:
            self.corpus_chunks = chunks
            tokenized_corpus = [
                chunk['content'].lower().split() 
                for chunk in chunks
            ]
            self.bm25_index = BM25Okapi(tokenized_corpus)
            self._bm25_loaded = True
            logger.info(f"✓ BM25 index built")
        else:
            logger.warning("No chunks found!")
    
    def semantic_search(self, query: str, top_k: int = None) -> List[tuple]:
        """
        Perform semantic search using Qdrant
        
        Args:
            query: Search query
            top_k: Number of results
        
        Returns:
            List of (chunk_id, score) tuples
        """
        top_k = top_k or self.top_k * 2  # Get extra for reranking
        
        # Generate query embedding
        query_vector = self.embedding_model.encode(query).tolist()
        
        # Search Qdrant (try both old and new API)
        try:
            # Try new API (v1.8+)
            from qdrant_client.models import PointStruct, Filter, FieldCondition, Range
            search_results = self.qdrant_client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k
            ).points
        except AttributeError:
            # Fallback to old API
            search_results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k
            )
        
        return [(str(hit.id), hit.score) for hit in search_results]
    
    def bm25_search(self, query: str, top_k: int = None) -> List[tuple]:
        """
        Perform BM25 keyword search
        
        Args:
            query: Search query
            top_k: Number of results
        
        Returns:
            List of (chunk_id, score) tuples
        """
        if not self._bm25_loaded:
            logger.warning("BM25 index not loaded! Call load_corpus() first.")
            return []
        
        top_k = top_k or self.top_k * 2
        
        # Tokenize query
        query_tokens = query.lower().split()
        
        # Get BM25 scores
        bm25_scores = self.bm25_index.get_scores(query_tokens)
        
        # Get top indices
        top_indices = np.argsort(bm25_scores)[::-1][:top_k]
        
        # Return results with non-zero scores
        results = []
        for idx in top_indices:
            if bm25_scores[idx] > 0:
                chunk_id = self.corpus_chunks[idx]['chunk_id']
                results.append((chunk_id, bm25_scores[idx]))
        
        return results
    
    def normalize_scores(self, scores: List[float]) -> List[float]:
        """Normalize scores to 0-1 range using min-max scaling"""
        if not scores or len(scores) == 0:
            return []
        
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            return [1.0] * len(scores)
        
        return [(s - min_score) / (max_score - min_score) for s in scores]
    
    def hybrid_search(
        self,
        query: str,
        alpha: float = None,
        top_k: int = None,
        ticker: str = None
    ) -> List[SearchResult]:
        """
        Perform hybrid search (Semantic + BM25)
        
        Args:
            query: Search query
            alpha: Weight for semantic (override default)
            top_k: Number of results (override default)
            ticker: Filter by company ticker
        
        Returns:
            Sorted list of SearchResult objects
        """
        alpha = alpha if alpha is not None else self.alpha
        top_k = top_k or self.top_k
        
        if not self._bm25_loaded:
            logger.warning("BM25 not loaded, using pure semantic search")
            alpha = 1.0  # Force pure semantic
        
        # 1. Semantic Search
        semantic_results = self.semantic_search(query, top_k=20)
        semantic_dict = {cid: score for cid, score in semantic_results}
        
        # 2. BM25 Search
        if alpha < 1.0 and self._bm25_loaded:
            bm25_results = self.bm25_search(query, top_k=20)
            bm25_dict = {cid: score for cid, score in bm25_results}
        else:
            bm25_dict = {}
        
        # 3. Combine chunk IDs
        all_chunk_ids = set(semantic_dict.keys()) | set(bm25_dict.keys())
        
        # 4. Normalize scores
        semantic_scores = [semantic_dict.get(cid, 0) for cid in all_chunk_ids]
        bm25_scores = [bm25_dict.get(cid, 0) for cid in all_chunk_ids]
        
        normalized_semantic = dict(zip(all_chunk_ids, self.normalize_scores(semantic_scores)))
        normalized_bm25 = dict(zip(all_chunk_ids, self.normalize_scores(bm25_scores)))
        
        # 5. Calculate hybrid scores
        hybrid_results = []
        
        for chunk_id in all_chunk_ids:
            sem_score = normalized_semantic[chunk_id]
            bm25_score = normalized_bm25[chunk_id]
            hybrid_score = alpha * sem_score + (1 - alpha) * bm25_score
            
            # Get chunk data
            chunk_data = self.chunk_map.get(chunk_id)
            if not chunk_data:
                # Fallback: fetch from Qdrant
                try:
                    point = self.qdrant_client.retrieve(
                        collection_name=self.collection_name,
                        ids=[chunk_id],
                        with_payload=True
                    )[0]
                    chunk_data = {
                        'chunk_id': chunk_id,
                        'content': point.payload.get('text', ''),
                        'metadata': point.payload
                    }
                    self.chunk_map[chunk_id] = chunk_data
                except:
                    continue
            
            # Filter by ticker if specified
            if ticker and chunk_data['metadata'].get('ticker') != ticker:
                continue
            
            hybrid_results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    content=chunk_data['content'],
                    metadata=chunk_data['metadata'],
                    semantic_score=sem_score,
                    bm25_score=bm25_score,
                    hybrid_score=hybrid_score,
                    rank=0
                )
            )
        
        # 6. Sort and assign ranks
        hybrid_results.sort(key=lambda x: x.hybrid_score, reverse=True)
        for rank, result in enumerate(hybrid_results[:top_k], start=1):
            result.rank = rank
        
        return hybrid_results[:top_k]
    
    def search(
        self,
        query: str,
        alpha: float = None,
        top_k: int = None,
        ticker: str = None,
        verbose: bool = True
    ) -> List[SearchResult]:
        """
        Main search interface (called by Analyzer Agent)
        
        Args:
            query: Search query (from Analyzer's sub-query)
            alpha: Hybrid weight (override)
            top_k: Number of results (override)
            ticker: Filter by company
            verbose: Print results
        
        Returns:
            List of SearchResult objects
        """
        results = self.hybrid_search(query, alpha, top_k, ticker)
        
        if verbose:
            self._print_results(query, results, alpha or self.alpha)
        
        return results
    
    def _print_results(self, query: str, results: List[SearchResult], alpha: float):
        """Pretty print search results"""
        print(f"\n{'='*80}")
        print(f"🔍 Query: {query}")
        print(f"📊 Alpha: {alpha:.2f} | Results: {len(results)}")
        print(f"{'='*80}\n")
        
        for result in results:
            ticker = result.metadata.get('ticker', 'N/A')
            source = result.metadata.get('source_type', 'N/A')
            
            print(f"#{result.rank} [{ticker}] {source.upper()}")
            print(f"   Hybrid: {result.hybrid_score:.3f} "
                  f"(Sem: {result.semantic_score:.3f}, BM25: {result.bm25_score:.3f})")
            print(f"   {result.content[:200]}...")
            print()


# Standalone testing
if __name__ == "__main__":
    # Initialize agent
    agent = ResearcherAgent(
        qdrant_host='localhost',
        alpha=0.5,
        top_k=5
    )
    
    # Load corpus
    print("\n🔄 Loading corpus from Qdrant...")
    agent.load_corpus()
    
    # Test queries
    test_queries = [
        "What are Google's main revenue sources?",
        "regulatory risks facing Alphabet",
        "AI and machine learning investments",
        "advertising business model",
        "YouTube monetization strategy"
    ]
    
    for query in test_queries:
        results = agent.search(query, verbose=True)
        input("\nPress Enter for next query...")