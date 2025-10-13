from __future__ import annotations
from typing import Any, Dict, Optional, Set

def answer_numeric(
    q: str,
    company: Optional[str],
    since: Optional[str],
    forms: Set[str],
    config: dict
) -> Dict[str, Any]:
    """
    TODO: parse query into concept + period and SELECT from DB.
    For now, return a structured 'not_implemented' response.
    """
    return {
        "type": "numeric",
        "query": q,
        "status": "not_implemented",
        "hint": "Implement SQL over the 'facts' table parsed from Inline XBRL.",
        "sources": []
    }
