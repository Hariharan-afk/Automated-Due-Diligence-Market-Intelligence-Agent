#io.py
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Iterable


def ensure_dir(p: str | Path) -> Path:
    path = Path(p)
    path.mkdir(parents=True, exist_ok=True)
    return path


def sha256_of_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def write_jsonl_line(path: str | Path, obj: dict) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    with p.open("a", encoding="utf-8") as f:
        f.write(json_dumps(obj) + "\n")


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
