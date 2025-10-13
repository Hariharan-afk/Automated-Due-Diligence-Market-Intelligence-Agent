#!/usr/bin/env python3
"""
query_demo.py

Quick demo CLI:
- If the question looks numeric (KPIs), answer deterministically from XBRL facts.
- Otherwise, perform hybrid retrieval (BM25 + vectors), then LLM compose with citations.
"""
from __future__ import annotations
import argparse
import json
import logging
import sys
from typing import Iterable, Optional, Set

from dd_agent.config import load_config, get_env
from dd_agent.retrieval.router import classify_query
from dd_agent.retrieval.facts_query import answer_numeric
from dd_agent.retrieval.rag import hybrid_answer
from dd_agent.utils.logging import setup_logging


def _parse_forms(csv: Optional[str]) -> Set[str]:
    if not csv:
        return {"10-K", "10-Q"}
    return {s.strip().upper() for s in csv.split(",") if s.strip()}


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Query demo: numeric router + hybrid RAG with citations.")
    ap.add_argument("--company", help="Optional company filter (ticker/name).")
    ap.add_argument("--forms", default="10-K,10-Q", help="Restrict forms for retrieval.")
    ap.add_argument("--since", help="Restrict filings by date (YYYY-MM-DD).")
    ap.add_argument("--k", type=int, default=6, help="Top-k chunks to retrieve.")
    ap.add_argument("--q", required=True, help="User question.")
    ap.add_argument("--no-llm", action="store_true", help="Skip LLM; print retrieved contexts only.")
    ap.add_argument("--config", default="configs/edgar.defaults.yaml")
    ap.add_argument("--log-config", default="configs/logging.yaml")
    return ap


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    setup_logging(args.log_config)
    log = logging.getLogger("query_demo")

    cfg = load_config(args.config)
    env = get_env()
    forms = _parse_forms(args.forms)

    qtype = classify_query(args.q)
    if qtype == "numeric":
        # Deterministic query path (XBRL facts via SQL)
        ans = answer_numeric(args.q, company=args.company, since=args.since, forms=forms, config=cfg)
        print(json.dumps(ans, indent=2))
        return 0

    # Narrative / qualitative → hybrid retrieval then LLM compose
    ans = hybrid_answer(
        query=args.q,
        filters={"company": args.company, "forms": sorted(forms), "since": args.since},
        k=args.k,
        config=cfg,
        no_llm=args.no_llm,
    )
    print(json.dumps(ans, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
