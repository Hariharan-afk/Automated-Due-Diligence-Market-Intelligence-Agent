from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np


class _JsonStore:
    """Very simple JSONL-based store (fallback when FAISS/pgvector not used)."""

    def __init__(self, root: Path, alias: str):
        self.root = root
        self.alias = alias
        self.file = root / f"{alias}.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def upsert(self, ids: List[str], vectors: List[List[float]], metadatas: List[Dict], collection: Optional[str] = None):
        with self.file.open("a", encoding="utf-8") as f:
            for i, v, m in zip(ids, vectors, metadatas):
                f.write(json.dumps({"id": i, "vec": v, "meta": m}) + "\n")

    def create_collection(self, name: str, if_not_exists: bool = True):
        # no-op for JSON fallback
        pass

    def temp_collection_name(self) -> str:
        return f"{self.alias}_tmp"

    def default_collection_alias(self) -> str:
        return self.alias


def get_store(cfg: dict, backend: Optional[str] = None, rebuild: bool = False):
    backend = backend or cfg["vector"]["backend"]
    alias = cfg["vector"]["collection_alias"]
    root = Path(cfg["paths"]["vectors_root"])
    if backend == "faiss":
        try:
            import faiss  # noqa
            # TODO: implement FAISS-backed store; for now, use JSON fallback
            return _JsonStore(root, alias)
        except Exception:
            return _JsonStore(root, alias)
    elif backend == "pgvector":
        # TODO: implement pgvector adapter. For now, use JSON fallback
        return _JsonStore(root, alias)
    else:
        return _JsonStore(root, alias)


def atomic_swap_collections(store, src: str, dst_alias: str):
    # No-op for JSON fallback. For real backends, update alias/symlink atomically.
    return
