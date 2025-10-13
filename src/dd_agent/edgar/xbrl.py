# xbrl.py
from __future__ import annotations
from pathlib import Path
from typing import Optional

def extract_facts_if_present(cik: str, accession: str, config: dict, env) -> Optional[int]:
    """
    Try to find Inline XBRL instance(s) in raw folder and extract facts.
    Minimal placeholder: returns None (no-op) if not implemented.
    TODO: integrate Arelle to parse instance and write parquet + DB.
    """
    # Example idea:
    # from arelle import CntlrCmdLine
    # ...
    raw = Path(config["paths"]["raw_root"]) / f"{int(cik):010d}" / accession
    # Detect .xml / .htm with ix: tags; for now, return None to indicate skipped.
    return None
