import sys
sys.path.append('.')

from typing import List, Dict
import numpy as np
from src.agents.base_agent import BaseAgent
from src.tools.hybrid_search import HybridSearchEngine
from src.tools.reranker import Reranker
from src.config import SEARCH_CONFIG
from src.model_validation.bias_mitigator import BiasMitigator

class ResearcherAgent(BaseAgent):
    """Retrieves relevant information from Qdrant"""
    
    def __init__(self, search_engine: HybridSearchEngine, reranker: Reranker):
        super().__init__("Researcher")
        self.search_engine = search_engine
        self.reranker = reranker
        self.initial_k = SEARCH_CONFIG["initial_k"]
        self.final_k = SEARCH_CONFIG["final_k"]
        self.mitigator = BiasMitigator()
    
    def execute(self, sub_queries: List[str]) -> List[Dict]:
        """
        Execute hybrid search + re-ranking for each sub-query
        
        Args:
            sub_queries: List of sub-queries from Analyser
        
        Returns:
            List of retrieved chunks with metadata
        """
        self.log(f"Researching {len(sub_queries)} sub-queries...")
        
        all_results = []
        
        for i, query in enumerate(sub_queries, 1):
            self.log(f"Sub-query {i}: '{query}'")
            
            # Hybrid search
            candidates = self.search_engine.search(query, top_k=self.initial_k)
            
            # Re-rank
            final_results = self.reranker.rerank(query, candidates, top_k=self.final_k)
            
            # BIAS MITIGATION
            # Attempt to detect group from query (simple heuristic)
            detected_group = None
            for group_id in self.mitigator.bias_map.keys():
                if group_id.lower() in query.lower():
                    detected_group = group_id
                    break
            
            if detected_group:
                self.log(f"  → Detected group '{detected_group}' - applying bias mitigation")
                final_results = self.mitigator.adjust_scores(final_results, detected_group)
            
            if final_results:
                avg_score = np.mean([r['final_score'] for r in final_results])
                self.log(f"  → Retrieved {len(final_results)} chunks (avg score: {avg_score:.3f})")
            else:
                self.log(f"  → No results found")
            
            # Add sub-query context
            for result in final_results:
                result['sub_query'] = query
            
            all_results.extend(final_results)
        
        self.log(f"Total chunks retrieved: {len(all_results)}")
        return all_results