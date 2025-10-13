#!/usr/bin/env python3
"""
index_filings.py

Read derived Markdown + section index, create RAG chunks, embed, and upsert
into the configured vector backend (pgvector or FAISS).
"""
from __future__ import annotations
import argparse
import logging
import sys
from typing import Iterable, Optional, Set

from dd_agent.config import load_config, get_env
from dd_agent.indexing.embed import get_embedder, embed_texts_batched
from dd_agent.indexing.vectorstore import get_store
from dd_agent.utils.text import iterate_chunks_from_sections
from dd_agent.utils.logging import setup_logging


def _parse_forms(csv: Optional[str]) -> Set[str]:
    if not csv:
        return {"10-K", "10-Q"}
    return {s.strip().upper() for s in csv.split(",") if s.strip()}


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Embed and index filings into a vector store.")
    ap.add_argument("--since", help="Only index filings since YYYY-MM-DD.")
    ap.add_argument("--forms", default="10-K,10-Q", help="Comma-separated forms to include.")
    ap.add_argument("--limit", type=int, default=100000, help="Maximum number of chunks to index.")
    ap.add_argument("--backend", choices=["pgvector", "faiss"], help="Override vector backend from config.")
    ap.add_argument("--rebuild", action="store_true", help="Drop and recreate target collection/index.")
    ap.add_argument("--batch-size", type=int, default=64, help="Embedding batch size.")
    ap.add_argument("--config", default="configs/edgar.defaults.yaml")
    ap.add_argument("--log-config", default="configs/logging.yaml")
    return ap


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    setup_logging(args.log_config)
    log = logging.getLogger("index_filings")

    cfg = load_config(args.config)
    env = get_env()
    forms = _parse_forms(args.forms)

    store = get_store(cfg, backend=args.backend, rebuild=args.rebuild)
    embedder = get_embedder(cfg)  # encapsulates model name/device in config

    n = 0
    batch_texts, batch_metas, batch_ids = [], [], []

    for chunk in iterate_chunks_from_sections(
        since=args.since,
        include_forms=forms,
        cfg=cfg,
    ):
        batch_texts.append(chunk.text)
        batch_metas.append(chunk.meta)
        batch_ids.append(chunk.id)
        if len(batch_texts) >= args.batch_size:
            vectors = embed_texts_batched(embedder, batch_texts)
            store.upsert(ids=batch_ids, vectors=vectors, metadatas=batch_metas)
            n += len(batch_texts)
            log.info("Indexed chunks: %d", n)
            batch_texts, batch_metas, batch_ids = [], [], []

        if n >= args.limit:
            break

    # Flush remainder
    if batch_texts:
        vectors = embed_texts_batched(embedder, batch_texts)
        store.upsert(ids=batch_ids, vectors=vectors, metadatas=batch_metas)
        n += len(batch_texts)

    log.info("Done. Total indexed chunks=%d", n)
    return 0 if n > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
