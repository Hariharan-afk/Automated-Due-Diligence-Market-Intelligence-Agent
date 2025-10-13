from __future__ import annotations
import re

NUMERIC_HINTS = [
    r"\b(revenue|net income|eps|ebitda|cash flow|gross margin|opex|capex|operating income)\b",
    r"\b(how much|what was|amount|value|figure)\b",
    r"\bFY\d{2,4}\b|\b20\d{2}\b",
]

def classify_query(q: str) -> str:
    text = q.lower()
    hits = sum(bool(re.search(pat, text)) for pat in NUMERIC_HINTS)
    return "numeric" if hits >= 1 else "narrative"
