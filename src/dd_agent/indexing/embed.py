from __future__ import annotations
from typing import Iterable, List

def get_embedder(cfg: dict, override_model: str | None = None):
    """
    Returns a callable: texts[list[str]] -> list[list[float]]
    Tries sentence-transformers; falls back to a tiny hashing embed.
    """
    model_name = override_model or cfg["embed"]["model"]
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
        return lambda texts: model.encode(texts, show_progress_bar=False, normalize_embeddings=True).tolist()
    except Exception:
        # Fallback: simple hash-based embedding (not good, but keeps pipeline unblocked)
        import numpy as np
        def _hash_embed(texts: Iterable[str]) -> List[List[float]]:
            vecs = []
            for t in texts:
                h = abs(hash(t)) % (10**8)
                vecs.append([float(h % 997) / 997.0] * 384)
            return vecs
        return _hash_embed


def embed_texts_batched(embedder, texts: List[str]) -> List[List[float]]:
    return embedder(texts)
