from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Set

import re
import json


@dataclass
class Chunk:
    id: str
    text: str
    meta: Dict


SEC_SECTION_RE = re.compile(
    r"(?im)^\s*item\s+(1a?|7a?)\.\s*(.+?)$"
)  # Item 1, 1A, 7, 7A (simple baseline)


def _load_sections_index(path: Path) -> List[Dict]:
    return json.loads(path.read_text())


def _load_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _section_chunks(text: str, section_name: str, cfg: dict) -> List[str]:
    max_tokens = int(cfg["edgar"]["chunk_tokens"])
    overlap = int(cfg["edgar"]["chunk_overlap"])
    # naive char-based chunking; replace with token-aware later
    max_chars = max_tokens * 4  # rough proxy
    ovl_chars = overlap * 4
    chunks: List[str] = []
    i = 0
    while i < len(text):
        j = min(len(text), i + max_chars)
        chunks.append(text[i:j])
        i = j - ovl_chars
        if i < 0:
            i = 0
        if j == len(text):
            break
    return chunks


def iterate_chunks_from_sections(
    since: Optional[str],
    include_forms: Set[str],
    cfg: dict,
) -> Iterator[Chunk]:
    derived_root = Path(cfg["paths"]["derived_root"])
    for cik_dir in derived_root.glob("*"):
        for acc_dir in cik_dir.glob("*"):
            sections_index = acc_dir / "sections" / "index.json"
            md_path = acc_dir / "text" / "cleaned.md"
            meta_path = acc_dir / "meta.json"
            if not sections_index.exists() or not md_path.exists():
                continue
            meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            if include_forms and meta.get("form") not in include_forms:
                continue
            sections = _load_sections_index(sections_index)
            full_text = _load_markdown(md_path)
            for s in sections:
                s_text = full_text[s["start_char"]: s["end_char"]]
                for n, ch in enumerate(_section_chunks(s_text, s["section"], cfg)):
                    cid = f'{meta.get("cik","")}_{meta.get("accession","")}_{s["section"]}_{n}'
                    yield Chunk(
                        id=cid,
                        text=ch,
                        meta={
                            "cik": meta.get("cik"),
                            "accession": meta.get("accession"),
                            "form": meta.get("form"),
                            "filing_date": meta.get("filing_date"),
                            "section": s["section"],
                            "chunk_id": n,
                            "url": meta.get("primary_doc_url"),
                        },
                    )


def all_chunks_iter(
    since: Optional[str],
    forms: Optional[Set[str]],
    cfg: dict,
) -> Iterator[Chunk]:
    include = forms or set()
    yield from iterate_chunks_from_sections(since=since, include_forms=include, cfg=cfg)
