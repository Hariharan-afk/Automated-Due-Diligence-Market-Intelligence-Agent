"""
tools/reranker.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Re-ranking using Gemini Pro (Listwise LLM Ranking)
"""

import sys
sys.path.append('.')

from typing import List, Dict
import json
from src.tools.local_client import get_local_client
from src.utils.helpers import extract_json

class Reranker:
    """Re-ranks search results using LLM (Gemini Pro)"""
    
    def __init__(self):
        print(f"🔄 Loading Gemini Pro Reranker...")
        self.client = get_local_client()
        print(f"✅ LLM Reranker ready")
    
    def rerank(self, query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        Re-rank candidates using Listwise LLM approach
        """
        if not candidates:
            return []
            
        print(f"📊 Reranking {len(candidates)} chunks with Gemini...")
        
        # 1. Prepare snippets for the prompt
        snippets_text = ""
        for i, c in enumerate(candidates):
            # 'raw_chunk' is the key from hybrid_search.py
            content = c.get('raw_chunk', '')[:300].replace("\n", " ") 
            snippets_text += f"[{i}] {content}\n\n"
            
        # 2. Construct Prompt (Listwise Ranking)
        prompt = f"""You are a Relevance Ranking Engine.
Query: "{query}"

Task: Rank the following snippets by relevance to the query.
- High relevance: Directly answers the query or contains key financial data.
- Low relevance: Tangential or unrelated.

Snippets:
{snippets_text}

Return a JSON object with a list of indices sorted by relevance (most relevant first).
Example: {{ "ranked_indices": [5, 0, 12, ...] }}
"""

        # 3. Call LLM
        try:
            response = self.client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0 # Strict determinism
            )
            
            # 4. Parse Result
            result = extract_json(response)
            ranked_indices = result.get("ranked_indices", [])
            
            # 5. Reorder Candidates
            reranked_candidates = []
            
            # Add top ranked items first
            seen_indices = set()
            for idx in ranked_indices:
                if 0 <= idx < len(candidates):
                    # Assign a synthetic score based on rank
                    candidates[idx]['rerank_score'] = 1.0 - (len(seen_indices) * 0.01)
                    reranked_candidates.append(candidates[idx])
                    seen_indices.add(idx)
                    
            # Add any missing items at the end
            for i in range(len(candidates)):
                if i not in seen_indices:
                    candidates[i]['rerank_score'] = 0.0
                    reranked_candidates.append(candidates[i])
            
            print(f"✅ Reranked top {top_k} results")
            return reranked_candidates[:top_k]
            
        except Exception as e:
            print(f"⚠️ Reranking failed: {e}. Fallback to original order.")
            # Fallback: just return top_k of original hybrid results
            return candidates[:top_k]
