import sys
sys.path.append('.')

from typing import List, Dict
import numpy as np
from src.agents.base_agent import BaseAgent
from src.tools.hybrid_search import HybridSearchEngine
from src.tools.reranker import Reranker
from src.config import SEARCH_CONFIG, AGENT_CONFIG
from src.model_validation.bias_mitigator import BiasMitigator
from src.tools.local_client import get_local_client

class ResearcherAgent(BaseAgent):
    """Retrieves relevant information from Qdrant"""
    
    def __init__(self, search_engine: HybridSearchEngine, reranker: Reranker):
        super().__init__("Researcher")
        self.search_engine = search_engine
        self.reranker = reranker
        self.temperature = AGENT_CONFIG["researcher"]["temperature"]
        self.initial_k = SEARCH_CONFIG["initial_k"]
        self.final_k = SEARCH_CONFIG["final_k"]
        self.mitigator = BiasMitigator()
        self.qdrant_client = get_local_client()
    
    def execute(self, sub_queries: List[str], original_query: str) -> List[Dict]:
        """
        Execute Global Reranking Strategy:
        1. Retrieve chunks for all sub-queries (Aggregation)
        2. Deduplicate
        3. Global Rerank against original_query
        """
        self.log(f"🔎 Researching {len(sub_queries)} sub-queries for Global Reranking...")
        
        all_candidates = []
        target_sources = ['sec', 'news', 'wikipedia']
        
        # 1. AGGREGATE CANDIDATES
        for i, query in enumerate(sub_queries, 1):
            self.log(f"  Query {i}: {query}")
            
            for source in target_sources:
                # Retrieve raw candidates (NO RERANKING YET)
                candidates = self.search_engine.search(
                    query, 
                    top_k=20, # Fetch more to have a good pool
                    source_filter=source
                )
                if candidates:
                    for c in candidates:
                        c['retrieved_for'] = query # Track provenance
                    all_candidates.extend(candidates)
        
        # 2. DEDUPLICATE
        unique_candidates = {}
        for c in all_candidates:
            # Keep the one with highest retrieval score if duplicate
            c_id = c['chunk_id']
            if c_id not in unique_candidates:
                unique_candidates[c_id] = c
            else:
                if c.get('final_score', 0) > unique_candidates[c_id].get('final_score', 0):
                    unique_candidates[c_id] = c
        
        pool = list(unique_candidates.values())
        self.log(f"📥 Aggregated Pool: {len(pool)} unique chunks. Starting Global Rerank...")
        
        if not pool:
            return []
            
        # 3. GLOBAL RERANK (Gemini 2.5 Pro)
        # Rerank the entire pool against the ORIGINAL wide query
        # We cap at 50 chunks sent to LLM to avoid context overflow/latency
        pool_for_rerank = sorted(pool, key=lambda x: x.get('final_score', 0), reverse=True)[:50]
        
        reranked_results = self.reranker.rerank(original_query, pool_for_rerank, top_k=self.final_k * 4) # Get Top 20 Global
        
        self.log(f"✅ Selected Top {len(reranked_results)} Global Chunks")
        return reranked_results