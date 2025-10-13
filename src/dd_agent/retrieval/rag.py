from __future__ import annotations
from typing import Any, Dict

def hybrid_answer(
    query: str,
    filters: Dict[str, Any],
    k: int,
    config: dict,
    no_llm: bool = False,
) -> Dict[str, Any]:
    """
    TODO: implement BM25 + vector search + rerank, then LLM compose.
    For now, return a structured stub that echoes filters.
    """
    return {
        "type": "narrative",
        "query": query,
        "k": k,
        "filters": filters,
        "status": "not_implemented",
        "contexts": [],
        "answer": None if not no_llm else "LLM disabled; returning contexts only.",
        "sources": []
    }
