# normalize.py
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import json

from dd_agent.utils.io import ensure_dir


def cik10(cik: str | int) -> str:
    return f"{int(cik):010d}"


def raw_dir(cfg: dict, cik: str, accession: str) -> Path:
    return Path(cfg["paths"]["raw_root"]) / cik10(cik) / accession


def derived_dir(cfg: dict, cik: str, accession: str) -> Path:
    return Path(cfg["paths"]["derived_root"]) / cik10(cik) / accession


def _meta_path(cfg: dict, cik: str, accession: str) -> Path:
    return raw_dir(cfg, cik, accession) / "meta.json"


def read_meta(cfg: dict, cik: str, accession: str) -> Dict[str, Any]:
    mp = _meta_path(cfg, cik, accession)
    if not mp.exists():
        raise FileNotFoundError(f"meta.json not found: {mp}")
    return json.loads(mp.read_text(encoding="utf-8"))


def resolve_raw_primary_path(cik: str, accession: str, cfg: dict | None = None) -> Path:
    """
    Prefer the primary filename recorded in meta.json; fall back to the biggest HTML-like file.
    """
    cfg = cfg or {"paths": {"raw_root": "artifacts/raw/edgar"}}
    rdir = raw_dir(cfg, cik, accession)

    # 1) try meta.json primary_doc
    mpath = rdir / "meta.json"
    if mpath.exists():
        try:
            meta = json.loads(mpath.read_text(encoding="utf-8"))
            fname = meta.get("primary_doc")
            if fname:
                p = rdir / fname
                if p.exists():
                    return p
        except Exception:
            pass

    # 2) fallback: biggest *.htm*
    htmls = sorted(rdir.glob("*.htm*"), key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
    if not htmls:
        raise FileNotFoundError(f"No HTML found in {rdir}")
    return htmls[0]


def list_accessions_since(cik: str, since: Optional[str]) -> List[str]:
    # Simple listing; ignoring date filter for now (TODO: persist file mtimes in manifest and filter)
    base = Path("artifacts/raw/edgar") / cik10(cik)
    if not base.exists():
        return []
    return sorted([p.name for p in base.iterdir() if p.is_dir()])


def list_accessions_from_meta(cik: str, cfg: dict) -> List[str]:
    """
    List accessions by presence of meta.json under artifacts/raw/edgar/{cik}/**/.
    This is the authoritative set of filings we fetched.
    """
    base = Path(cfg["paths"]["raw_root"]) / cik10(cik)
    if not base.exists():
        return []
    accs: List[str] = []
    for p in base.iterdir():
        if p.is_dir() and (p / "meta.json").exists():
            accs.append(p.name)
    return sorted(accs)


def processed_outputs_exist(cik: str, accession: str, cfg: dict) -> bool:
    """
    True if both cleaned Markdown and section index already exist.
    """
    d = derived_dir(cfg, cik, accession)
    md = d / "text" / "cleaned.md"
    idx = d / "sections" / "index.json"
    return md.exists() and idx.exists()