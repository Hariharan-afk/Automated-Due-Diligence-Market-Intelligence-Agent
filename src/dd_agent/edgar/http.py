#http.py
from __future__ import annotations
import os, time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry  # <-- correct import

_DEFAULT_ID = "dd-agent/0.1 (contact: your-email@example.com)"

def make_sec_session(identity: str | None = None, timeout: float = 30.0) -> requests.Session:
    ua = identity or os.getenv("SEC_IDENTITY") or _DEFAULT_ID
    s = requests.Session()
    s.headers.update({
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    })
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        status=5,
        backoff_factor=1.0,  # 1s, 2s, 4s, 8s...
        status_forcelist=(403, 429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    # Ensure default timeout on every request
    _orig = s.request
    def _req(method, url, **kw):
        kw.setdefault("timeout", timeout)
        return _orig(method, url, **kw)
    s.request = _req
    return s

def polite_get(session: requests.Session, url: str, rate_sleep: float = 0.3):
    r = session.get(url, allow_redirects=True)
    # If still forbidden, raise so caller can try fallback (index.json, submission .txt, etc.)
    if r.status_code == 403:
        r.raise_for_status()
    time.sleep(max(rate_sleep, 0.2))   # stay ≤ 5 req/sec
    return r
