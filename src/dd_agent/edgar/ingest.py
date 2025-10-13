from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict
import os

from dd_agent.utils.io import ensure_dir, sha256_of_file, write_jsonl_line, json_dumps
from dd_agent.edgar.http import make_sec_session, polite_get

log = logging.getLogger(__name__)
_SEC = None

def _sess():
    global _SEC
    if _SEC is None:
        _SEC = make_sec_session()  # pulls SEC_IDENTITY from env
    return _SEC

def _resolve_rate_sleep(env, config, default: float = 0.3) -> float:
    """
    Try to get rate sleep from (1) function arg 'env' (various shapes),
    (2) config dict, (3) OS env var RATE_SLEEP, else default.
    """
    # 1) env: dict-like
    try:
        if env is not None:
            if isinstance(env, dict):
                return float(env.get("RATE_SLEEP", default))
            # has attribute .get (e.g., SimpleNamespace with custom get)
            if hasattr(env, "get"):
                return float(env.get("RATE_SLEEP", default))
            # common attributes
            for attr in ("RATE_SLEEP", "rate_sleep"):
                if hasattr(env, attr):
                    return float(getattr(env, attr))
    except Exception:
        pass

    # 2) config dict
    try:
        if isinstance(config, dict):
            v = (
                config.get("rate_sleep")
                or config.get("http", {}).get("rate_sleep")
                or config.get("sec", {}).get("rate_sleep")
            )
            if v is not None:
                return float(v)
    except Exception:
        pass

    # 3) process env
    try:
        v = os.getenv("RATE_SLEEP")
        if v:
            return float(v)
    except Exception:
        pass

    return float(default)

def ensure_raw_dir(cik: str, accession: str, cfg: dict | None = None) -> Path:
    root = Path((cfg or {"paths":{"raw_root":"artifacts/raw/edgar"}})["paths"]["raw_root"])
    d = root / f"{int(cik):010d}" / accession
    ensure_dir(d)
    return d

def build_meta_from_filing_row(cik: str, row: Dict) -> Dict:
    # Be robust if cik is missing in row
    try:
        cik_fmt = f"{int(cik):010d}" if cik not in (None, "",) else None
    except Exception:
        cik_fmt = None
    return {
        "cik": cik_fmt,
        "accession": row["accessionNumber"],
        "form": row["form"],
        "filing_date": row["filingDate"],
        "report_date": row.get("reportDate") or None,
        "primary_doc": row["primaryDocument"],
        "primary_doc_url": row["url"],
    }

def _http_download(url: str, dest: Path, rate_sleep: float = 0.3) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = polite_get(_sess(), url, rate_sleep=rate_sleep)
    r.raise_for_status()
    dest.write_bytes(r.content)


def download_primary_and_companions(
    filing_row: Dict,
    raw_dir: Path,
    force: bool,
    download_companions: bool,
    config: dict,
    env,
) -> None:
    rate_sleep = _resolve_rate_sleep(env, config, default=0.3)

    primary_url = filing_row["url"]
    primary_path = raw_dir / Path(primary_url).name

    if primary_path.exists() and not force:
        log.info("Primary already exists: %s", primary_path)
    else:
        try:
            _http_download(primary_url, primary_path, rate_sleep=rate_sleep)
        except Exception as e:
            log.warning("Primary  download failed (%s). Trying fallbacks…", e)
            base = primary_url.rsplit("/", 1)[0]
            # Try folder index.json
            try:
                _http_download(f"{base}/index.json", raw_dir / "index.json", rate_sleep=rate_sleep)
            except Exception:
                pass
            # Try complete submission .txt
            try:
                accnodash = base.rstrip("/").split("/")[-1]
                _http_download(f"{base}/{accnodash}.txt", raw_dir / f"{accnodash}.txt", rate_sleep=rate_sleep)
            except Exception:
                pass

    if download_companions:
        base = primary_url.rsplit("/", 1)[0]
        for rel in ("index.json", "FilingSummary.xml"):
            try:
                _http_download(f"{base}/{rel}", raw_dir / rel, rate_sleep=rate_sleep)
            except Exception:
                pass


def write_manifest_line(meta: Dict, raw_dir: Path) -> None:
    primary = raw_dir / meta["primary_doc"]
    if primary.exists():
        meta["primary_sha256"] = sha256_of_file(primary)
        meta["primary_size"] = primary.stat().st_size
    write_jsonl_line("artifacts/manifests/ingest_manifest.jsonl", meta)
