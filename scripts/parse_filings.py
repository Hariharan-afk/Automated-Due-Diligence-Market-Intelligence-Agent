#!/usr/bin/env python3
"""
parse_filings.py

Transform raw filing HTML into cleaned Markdown with a robust section index,
and optionally extract Inline XBRL facts into a tidy table (and/or database).
"""
from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable, List, Optional

repo_root = Path(__file__).resolve().parent
src_dir = str(repo_root.parent / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from dd_agent.config import load_config, get_env
from dd_agent.edgar.parse_html import html_to_markdown_sectioned
from dd_agent.edgar.xbrl import extract_facts_if_present
from dd_agent.utils.logging import setup_logging
from dd_agent.edgar.normalize import (
    list_accessions_since,
    resolve_raw_primary_path,
    derived_dir,
    processed_outputs_exist,
    list_accessions_from_meta,
)



def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Parse raw filings into Markdown + sections, extract XBRL facts.")
    ap.add_argument("--cik", required=True, help="Target CIK (with or without leading zeros).")
    src = ap.add_mutually_exclusive_group(required=False)
    src.add_argument("--accession", action="append", help="Specific accession (repeatable).")
    src.add_argument("--since", help="Parse all filings modified since YYYY-MM-DD.")
    ap.add_argument("--overwrite", action="store_true", help="Rebuild derived even if it exists.")
    ap.add_argument("--no-xbrl", action="store_true", help="Skip XBRL extraction.")
    ap.add_argument("--config", default="configs/edgar.defaults.yaml")
    ap.add_argument("--log-config", default="configs/logging.yaml")
    return ap


def _targets(cik: str, accessions: Optional[List[str]], since: Optional[str], cfg: dict, overwrite: bool) -> List[str]:
    """
    Selection semantics:
    - If accessions are explicitly provided -> use exactly those.
    - Else if --since provided -> use list_accessions_since (your existing policy).
    - Else (default "normal run"): scan meta.json under raw and choose:
        * only UNPROCESSED accessions (outputs missing)
        * OR ALL if overwrite=True
    """
    if accessions:
        return accessions

    if since:
        return list_accessions_since(cik=cik, since=since)

    # Default behavior: auto-scan meta and pick unprocessed (or all if overwrite)
    accs = list_accessions_from_meta(cik, cfg)
    if overwrite:
        return accs
    return [a for a in accs if not processed_outputs_exist(cik, a, cfg)]


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    setup_logging(args.log_config)
    log = logging.getLogger("parse_filings")

    cfg = load_config(args.config)
    env = get_env()
    cik10 = f"{int(args.cik):010d}"

    accs = _targets(cik10, args.accession, args.since, cfg, args.overwrite)
    if not accs:
        log.info("Nothing to do: no unprocessed filings found (use --overwrite to force).")
        return 0

    parsed = 0
    for acc in accs:
        try:
            raw_path = resolve_raw_primary_path(cik10, acc, cfg)
            md_path, sections_index_path = html_to_markdown_sectioned(
                cik=cik10,
                accession=acc,
                raw_primary_path=raw_path,
                overwrite=args.overwrite,
                config=cfg,
            )
            parsed += 1
            log.info("Parsed %s → %s", acc, md_path)

            if not args.no_xbrl:
                n_facts = extract_facts_if_present(cik=cik10, accession=acc, config=cfg, env=env)
                if n_facts is not None:
                    log.info("Extracted %d XBRL facts for %s", n_facts, acc)

        except FileNotFoundError:
            log.warning("Raw primary HTML not found for %s; did you run fetch?", acc)
        except Exception as e:
            log.exception("Failed to parse %s: %s", acc, e)

    log.info("Done. Parsed=%d", parsed)
    return 0 if parsed > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
