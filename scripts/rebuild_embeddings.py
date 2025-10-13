#!/usr/bin/env python3
"""
rebuild_embeddings.py

Re-embed existing chunks using a new embedding model or updated chunking policy.
Supports atomic swap so query traffic can move to the new collection seamlessly.
"""
from __future__ import annotations
import argparse
import logging
import sys
from typing import Iterable, Optional, Set

from dd_agent.config import load_config, get_env
from dd_agent.indexing.embed import get_embedder, embed_texts_batched
from dd_agent.indexing.vectorstore import get_store, atomic_swap_collections
from dd_agent.utils.text import all_chunks_iter
from dd_agent.utils.logging import setup_logging


def _parse_forms(csv: Optional[str]) -> Optional[Set[str]]:
    if not csv:
        return None
    return {s.strip().upper() for s in csv.split(",") if s.strip()}


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Rebuild embeddings and atomically swap the active collection.")
    ap.add_argument("--model", help="Embedding model name to override config.")
    ap.add_argument("--filter-forms", help="Restrict to specific forms, e.g., '10-K,10-Q'.")
    ap.add_argument("--since", help="Only re-embed chunks since YYYY-MM-DD.")
    ap.add_argument("--dry-run", action="store_true", help="Do not write anything; just report counts.")
    ap.add_argument("--atomic-swap", action="store_true", help="Swap active collection alias on completion.")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--config", default="configs/edgar.defaults.yaml")
    ap.add_argument("--log-config", default="configs/logging.yaml")
    return ap


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    setup_logging(args.log_config)
    log = logging.getLogger("rebuild_embeddings")

    cfg = load_config(args.config)
    env = get_env()
    forms = _parse_forms(args.filter_forms)

    # Enumerate all chunks with metadata (ids + text)
    chunks = list(all_chunks_iter(since=args.since, forms=forms, cfg=cfg))
    if args.dry_run:
        log.info("[dry-run] Would re-embed %d chunks", len(chunks))
        return 0

    embedder = get_embedder(cfg, override_model=args.model)
    store = get_store(cfg)
    tmp_name = store.temp_collection_name()

    store.create_collection(tmp_name, if_not_exists=True)

    batch_texts, batch_metas, batch_ids = [], [], []
    done = 0

    for ch in chunks:
        batch_texts.append(ch.text)
        batch_metas.append(ch.meta)
        batch_ids.append(ch.id)

        if len(batch_texts) >= args.batch_size:
            vecs = embed_texts_batched(embedder, batch_texts)
            store.upsert(collection=tmp_name, ids=batch_ids, vectors=vecs, metadatas=batch_metas)
            done += len(batch_texts)
            log.info("Re-embedded %d/%d", done, len(chunks))
            batch_texts, batch_metas, batch_ids = [], [], []

    if batch_texts:
        vecs = embed_texts_batched(embedder, batch_texts)
        store.upsert(collection=tmp_name, ids=batch_ids, vectors=vecs, metadatas=batch_metas)
        done += len(batch_texts)

    if args.atomic_swap:
        atomic_swap_collections(store, src=tmp_name, dst_alias=store.default_collection_alias())
        log.info("Atomic swap complete. Active collection now points to %s", tmp_name)
    else:
        log.info("Finished (no swap). Temp collection name: %s", tmp_name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
