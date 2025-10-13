from __future__ import annotations
import os
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None  # optional dependency


DEFAULTS = {
    "paths": {
        "artifacts": "artifacts",
        "raw_root": "artifacts/raw/edgar",
        "derived_root": "artifacts/derived/edgar",
        "vectors_root": "artifacts/vectors",
        "manifests_root": "artifacts/manifests",
    },
    "vector": {
        "backend": "faiss",  # or "pgvector"
        "collection_alias": "filings_vectors",
    },
    "edgar": {
        "rate_sleep": 0.4,
        "chunk_tokens": 1200,
        "chunk_overlap": 200,
    },
    "embed": {
        "model": "sentence-transformers/all-MiniLM-L6-v2"
    }
}


def load_config(path: str | os.PathLike) -> Dict[str, Any]:
    """Load YAML config and merge defaults."""
    p = Path(path)
    if not p.exists():
        return json.loads(json.dumps(DEFAULTS))  # deep copy
    data = yaml.safe_load(p.read_text()) or {}
    merged = DEFAULTS | data if isinstance(data, dict) else DEFAULTS
    # Shallow-merge dict sections present in data
    for k in DEFAULTS:
        if isinstance(DEFAULTS[k], dict):
            merged[k] = {**DEFAULTS[k], **(data.get(k, {}) if isinstance(data.get(k, {}), dict) else {})}
    return merged


@dataclass
class Env:
    SEC_USER_AGENT: str | None
    DATABASE_URL: str | None


def get_env() -> Env:
    """Load .env and environment variables once."""
    if load_dotenv:
        load_dotenv(override=False)
    return Env(
        SEC_USER_AGENT=os.getenv("SEC_USER_AGENT"),
        DATABASE_URL=os.getenv("DATABASE_URL"),
    )
