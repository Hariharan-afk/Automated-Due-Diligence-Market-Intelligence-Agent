#!/usr/bin/env python3
"""
fetch_filings.py

Download SEC 10-K/10-Q primary documents (and optional companions) into
artifacts/raw/edgar/{cik}/{accession}/... and append a JSONL line to
artifacts/manifests/ingest_manifest.jsonl.

This CLI is intentionally thin and delegates to dd_agent modules so you can
swap implementations without touching the interface.
"""
from __future__ import annotations
import argparse
import logging
import sys
import time
from typing import Iterable, Optional, Set
from pathlib import Path

# Ensure the project's `src/` directory is on sys.path so imports like
# `from dd_agent...` work when running this script directly (e.g.,
# `python scripts/fetch_filings.py`). This mirrors setting PYTHONPATH=./src
# but makes the script more user-friendly for local runs.
repo_root = Path(__file__).resolve().parent
# scripts/ is one level below the repo root, so go up one and add src/
src_dir = str(repo_root.parent / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Internal imports — you’ll implement these modules.
from dd_agent.config import load_config, get_env
from dd_agent.edgar.sec_filings import load_company_index, resolve_cik, find_10k_10q
from dd_agent.edgar.ingest import (
    ensure_raw_dir,
    download_primary_and_companions,
    write_manifest_line,
    build_meta_from_filing_row,
)
from dd_agent.utils.logging import setup_logging


def _parse_forms(csv: Optional[str]) -> Set[str]:
    if not csv:
        return {"10-K", "10-Q"}
    return {s.strip().upper() for s in csv.split(",") if s.strip()}


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Fetch SEC filings (10-K/10-Q) into artifacts/raw and log a manifest line."
    )
    ident = ap.add_mutually_exclusive_group(required=True)
    ident.add_argument("--company", help="Company name (as on EDGAR), e.g., 'Apple Inc.'")
    ident.add_argument("--ticker", help="Stock ticker, e.g., AAPL")
    ident.add_argument("--cik", help="Numerical CIK (with/without leading zeros)")

    timegrp = ap.add_mutually_exclusive_group(required=True)
    timegrp.add_argument("--year", type=int, help="Single calendar year, e.g., 2024")
    timegrp.add_argument("--start", help="Start date YYYY-MM-DD (inclusive)")
    ap.add_argument("--end", help="End date YYYY-MM-DD (inclusive). Required with --start")

    ap.add_argument("--forms", default="10-K,10-Q", help="Comma-separated forms. Default: 10-K,10-Q")
    ap.add_argument("--max", type=int, default=50, help="Max filings to download")
    ap.add_argument("--rate-sleep", type=float, default=0.4, help="Seconds to sleep between SEC requests")
    ap.add_argument("--force", action="store_true", help="Re-download even if file exists")
    ap.add_argument("--no-companions", action="store_true", help="Skip companion files (index, xbrl), download only primary")
    ap.add_argument("--config", default="configs/edgar.defaults.yaml", help="Path to config YAML")
    ap.add_argument("--log-config", default="configs/logging.yaml", help="Path to logging YAML")
    return ap


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    setup_logging(args.log_config)
    log = logging.getLogger("fetch_filings")

    cfg = load_config(args.config)
    env = get_env()  # picks up SEC_USER_AGENT etc. from .env or environment

    # Resolve identity → CIK
    if args.cik:
        cik = f"{int(args.cik):010d}"
        company_label = f"CIK {cik}"
    else:
        index = load_company_index(use_cache=True)
        q = args.ticker or args.company  # one is guaranteed by argparse
        cik_int = resolve_cik(q, index)
        if cik_int is None:
            log.error("Could not resolve CIK for query=%r", q)
            return 1
        cik = f"{cik_int:010d}"
        company_label = args.ticker or args.company

    if args.start and not args.end:
        log.error("--end is required when using --start")
        return 1

    forms = _parse_forms(args.forms)

    log.info("Fetching filings for %s (CIK=%s), forms=%s", company_label, cik, sorted(forms))
    filings = find_10k_10q(
        company_or_ticker=args.cik or (args.ticker or args.company),
        year=args.year,
        start=args.start,
        end=args.end,
    )
    if not filings:
        log.warning("No filings found for the given time window.")
        return 2

    fetched = 0
    for row in filings:
        if row["form"] not in forms:
            continue

        raw_dir = ensure_raw_dir(cik, row["accessionNumber"])
        meta = build_meta_from_filing_row(cik, row)

        try:
            # Download primary doc (+ optional companions)
            download_primary_and_companions(
                filing_row=row,
                raw_dir=raw_dir,
                force=args.force,
                download_companions=(not args.no_companions),
                config=cfg,
                env=env,
            )
            write_manifest_line(meta, raw_dir)
            fetched += 1
            log.info("Fetched %s %s (%s)", row["form"], row["filingDate"], row["accessionNumber"])
        except Exception as e:  # keep fetch loops resilient
            log.exception("Failed to fetch %s: %s", row["accessionNumber"], e)

        if fetched >= args.max:
            break
        time.sleep(max(0.0, args.rate_sleep))

    log.info("Done. Fetched=%d", fetched)
    return 0 if fetched > 0 else 2


if __name__ == "__main__":
    sys.exit(main())

