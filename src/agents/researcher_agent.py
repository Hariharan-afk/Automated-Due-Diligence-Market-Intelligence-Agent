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
    
    def execute(self, sub_queries: List[str]) -> List[Dict]:
        """
        Execute hybrid search + re-ranking for each sub-query
        Ensures diversity by fetching from SEC, News, and Wikipedia.
        """
        self.log(f"Researching {len(sub_queries)} sub-queries...")
        
        all_results = []
        
        # Define sources to target
        target_sources = ['sec', 'news', 'wikipedia']
        # Dynamic selection config
        min_score_threshold = -5.0  # Lowered threshold to allow more chunks (since scores are around -4 to -6)
        max_chunks_per_source = 10  # Safety cap
        
        for i, query in enumerate(sub_queries, 1):
            self.log(f"Sub-query {i}: '{query}'")
            sub_query_results = []
            
            for source in target_sources:
                # Search with filter
                candidates = self.search_engine.search(
                    query, 
                    top_k=self.initial_k, 
                    source_filter=source
                )
                
                if candidates:
                    # Re-rank MANY candidates (up to max safety cap)
                    reranked = self.reranker.rerank(query, candidates, top_k=max_chunks_per_source)
                    
                    # Apply Bias Mitigation (Boost underrepresented groups)
                    reranked = self.mitigator.adjust_scores_by_metadata(reranked)
                    
                    # Sync rerank_score with final_score if boosted (so they pass threshold)
                    for c in reranked:
                        if c.get('bias_boosted') and 'final_score' in c:
                             c['rerank_score'] = c['final_score']
                    
                    # Filter by Score Threshold
                    selected = [c for c in reranked if c['rerank_score'] > min_score_threshold]
                    
                    # If nothing meets threshold, keep at least the top 1 (best effort)
                    if not selected and reranked:
                        # Sort again just in case mitigation changed order (mitigator does sort, but safely)
                        reranked.sort(key=lambda x: x.get('rerank_score', -99), reverse=True)
                        selected = [reranked[0]]
                    
                    # Add sub_query to each selected result
                    for res in selected:
                        res['sub_query'] = query
                    
                    self.log(f"    → Found {len(selected)} chunks from {source.upper()} (threshold: {min_score_threshold})")
                    sub_query_results.extend(selected)
                else:
                    self.log(f"    → No chunks found for {source.upper()}")
            
            # 2. Also do a general search (no filter) to catch anything else relevant
            # general_candidates = self.search_engine.search(query, top_k=5)
            # general_reranked = self.reranker.rerank(query, general_candidates, top_k=2)
            # sub_query_results.extend(general_reranked)
            
            # Deduplicate by chunk_id
            seen_ids = set()
            unique_results = []
            for res in sub_query_results:
                if res['chunk_id'] not in seen_ids:
                    seen_ids.add(res['chunk_id'])
                    unique_results.append(res)
            
            if unique_results:
                avg_score = np.mean([r['final_score'] for r in unique_results])
                self.log(f"  → Retrieved {len(unique_results)} unique chunks (avg score: {avg_score:.3f})")
            else:
                self.log(f"  → No results found")
            
            all_results.extend(unique_results)
        
        self.log(f"Total chunks retrieved: {len(all_results)}")
        return all_results