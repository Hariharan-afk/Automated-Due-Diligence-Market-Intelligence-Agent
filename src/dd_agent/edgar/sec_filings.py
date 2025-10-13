# sec_filings.py
from __future__ import annotations
import datetime as dt
import json
import re
from pathlib import Path
from typing import Iterable, List, Dict, Optional

from dd_agent.edgar.http import make_sec_session, polite_get

# ---------- Config ----------

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL_TMPL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"

CACHE_DIR = Path(".sec_cache")
CACHE_DIR.mkdir(exist_ok=True)
TICKERS_CACHE = CACHE_DIR / "company_tickers.json"

_SEC = make_sec_session()  # shared, polite SEC session

# ---------- CIK resolution ----------

def load_company_index(use_cache: bool = True) -> List[Dict]:
    if use_cache and TICKERS_CACHE.exists():
        data = json.loads(TICKERS_CACHE.read_text())
    else:
        r = polite_get(_SEC, COMPANY_TICKERS_URL)
        r.raise_for_status()
        data = r.json()
        TICKERS_CACHE.write_text(json.dumps(data))
    rows = []
    for _, row in data.items():
        rows.append({
            "cik": int(row["cik_str"]),
            "ticker": str(row.get("ticker", "")).upper(),
            "name": str(row.get("title", "")).upper(),
        })
    return rows

def resolve_cik(query: str, company_index: List[Dict]) -> Optional[int]:
    """
    Resolve user query (ticker like 'AAPL' or company name like 'Apple') to a CIK.
    Strategy: exact ticker match -> name contains -> startswith -> fuzzy token match.
    """
    q = query.strip().upper()

    # exact ticker hit
    for row in company_index:
        if row["ticker"] and row["ticker"] == q:
            return row["cik"]

    # name contains
    contains = [r for r in company_index if q in r["name"]]
    if contains:
        return contains[0]["cik"]

    # name startswith
    starts = [r for r in company_index if r["name"].startswith(q)]
    if starts:
        return starts[0]["cik"]

    # token match (e.g., "ALPHABET INC CLASS A" vs "ALPHABET")
    tokens = set(re.findall(r"[A-Z0-9]+", q))
    best = None
    for r in company_index:
        name_tokens = set(r["name"].split())
        if tokens.issubset(name_tokens):
            best = r["cik"]
            break
    return best

# ---------- Submissions fetch & filter ----------
def fetch_submissions(cik: int) -> Dict:
    url = SUBMISSIONS_URL_TMPL.format(cik=cik)
    r = polite_get(_SEC, url)
    r.raise_for_status()
    return r.json()

def _iterate_recent(fj: Dict):
    """
    Yield row dicts from filings.recent (columnar arrays to row dicts).
    """
    recent = fj.get("filings", {}).get("recent", {})
    cols = ["form","filingDate","reportDate","accessionNumber","primaryDocument"]
    arrays = [recent.get(k, []) for k in cols]
    for i in range(min(len(a) for a in arrays)):
        yield {k: arrays[j][i] for j, k in enumerate(cols)}

def build_primary_doc_url(cik: int | str, accession_no: str, primary_doc: str) -> str:
    """
    Canonical EDGAR Archives path for the primary document in a submission.
    https://www.sec.gov/Archives/edgar/data/{CIK_no_leading_zeros}/{accessionNo_no_dashes}/{primaryDocument}
    """
    cik_no_zeros = str(int(cik))
    acc_nodash = accession_no.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_no_zeros}/{acc_nodash}/{primary_doc}"

def filings_in_range(
    filings_json: Dict,
    forms: Iterable[str],
    start: dt.date,
    end: dt.date,
) -> List[Dict]:
    """
    Filter recent filings by form type and filingDate within [start, end].
    Returns list of dicts with URL to the primary document.
    """
    hits = []
    for row in _iterate_recent(filings_json):
        if row["form"] not in forms:
            continue
        fdate = dt.date.fromisoformat(row["filingDate"])
        if not (start <= fdate <= end):
            continue
        url = build_primary_doc_url(filings_json["cik"], row["accessionNumber"], row["primaryDocument"])
        hits.append({
            "form": row["form"],
            "filingDate": row["filingDate"],
            "reportDate": row.get("reportDate", ""),
            "accessionNumber": row["accessionNumber"],
            "primaryDocument": row["primaryDocument"],
            "url": url,
        })
    # Sort newest first
    hits.sort(key=lambda d: d["filingDate"], reverse=True)
    return hits

def find_10k_10q(
    company_or_ticker: str,
    year: Optional[int] = None,
    start: Optional[str] = None,  # "YYYY-MM-DD"
    end: Optional[str]   = None,
) -> List[Dict]:
    """
    Main entry point: Return 10-K and 10-Q primary document URLs for a company
    and either a single year or a closed date range [start, end].
    """
    idx = load_company_index()
    cik = resolve_cik(company_or_ticker, idx)
    if cik is None:
        raise ValueError(f"Could not resolve CIK for '{company_or_ticker}'. Try exact ticker or official EDGAR name.")

    subs = fetch_submissions(cik)

    if year is not None:
        start_date = dt.date(year, 1, 1)
        end_date   = dt.date(year, 12, 31)
    else:
        if not start or not end:
            raise ValueError("Provide either 'year' OR both 'start' and 'end' (YYYY-MM-DD).")
        start_date = dt.date.fromisoformat(start)
        end_date   = dt.date.fromisoformat(end)

    return filings_in_range(subs, {"10-K", "10-Q"}, start_date, end_date)

if __name__ == "__main__":
    # Quick manual test:
    results = find_10k_10q("Alphabet", year=2024)
    for r in results:
        print(r["form"], r["filingDate"], "->", r["url"])
