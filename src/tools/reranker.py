"""
tools/reranker.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Re-ranking using cross-encoder
"""

import sys
sys.path.append('.')

from typing import List, Dict
from sentence_transformers import CrossEncoder
from src.config import SEARCH_CONFIG

class Reranker:
    """Re-ranks search results using cross-encoder"""
    
    def __init__(self):
        print(f"🔄 Loading re-ranker model...")
        self.model = CrossEncoder(SEARCH_CONFIG["reranker_model"])
        print(f"✅ Re-ranker ready")
    
    def rerank(self, query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        Re-rank candidates
        
        Args:
            query: Original query
            candidates: List of candidate chunks
            top_k: Number to return
        
        Returns:
            Top-k re-ranked results
        """
        if not candidates:
            return []
        
        # Create query-document pairs
        pairs = [[query, c['raw_chunk']] for c in candidates]
        
        # Get re-ranking scores
        scores = self.model.predict(pairs)
        
        # Attach scores
        for candidate, score in zip(candidates, scores):
            candidate['rerank_score'] = float(score)
            candidate['final_score'] = float(score)
        
        # Sort by rerank score
        candidates.sort(key=lambda x: x['rerank_score'], reverse=True)
        
        return candidates[:top_k]