# # parse_html.py
# from __future__ import annotations
# import re
# import json
# from pathlib import Path
# from typing import Tuple

# from bs4 import BeautifulSoup  # pip install beautifulsoup4

# from dd_agent.edgar.normalize import derived_dir
# from dd_agent.utils.io import ensure_dir


# SEC_ITEM_RE = re.compile(r"(?im)^\s*item\s+(1a?|7a?)\.\s+(.+?)$")


# def html_to_markdown_sectioned(
#     cik: str,
#     accession: str,
#     raw_primary_path: str | Path,
#     overwrite: bool,
#     config: dict,
# ) -> Tuple[Path, Path]:
#     """
#     Cleans HTML, converts to Markdown-like text (very simple), detects Item sections,
#     writes:
#       - derived/.../text/cleaned.md
#       - derived/.../sections/index.json (list of {section, start_char, end_char})
#     """
#     out_root = derived_dir(config, cik, accession)
#     text_dir = ensure_dir(out_root / "text")
#     sec_dir = ensure_dir(out_root / "sections")
#     md_out = text_dir / "cleaned.md"
#     idx_out = sec_dir / "index.json"

#     if md_out.exists() and idx_out.exists() and not overwrite:
#         return md_out, idx_out

#     # --- Clean HTML (strip scripts/styles) ---
#     html = Path(raw_primary_path).read_text(encoding="utf-8", errors="ignore")
#     soup = BeautifulSoup(html, "html.parser")
#     for tag in soup(["script", "style"]):
#         tag.decompose()
#     text = soup.get_text("\n")
#     # Normalize whitespace
#     text = re.sub(r"[ \t\r]+", " ", text)
#     text = re.sub(r"\n{3,}", "\n\n", text).strip()

#     # --- Detect sections (very simple regex markers) ---
#     # We record byte offsets to let chunker slice text deterministically
#     sections = []
#     for m in SEC_ITEM_RE.finditer(text):
#         title = m.group(0).strip()
#         start = m.start()
#         sections.append((title, start))

#     # Close each section with next start or EOF
#     ranges = []
#     for i, (title, start) in enumerate(sections):
#         end = sections[i + 1][1] if i + 1 < len(sections) else len(text)
#         ranges.append({"section": title, "start_char": start, "end_char": end})

#     md_out.write_text(text, encoding="utf-8")
#     idx_out.write_text(json.dumps(ranges, ensure_ascii=False, indent=2), encoding="utf-8")
#     return md_out, idx_out


# src/dd_agent/edgar/parse_html.py
# from __future__ import annotations
# import re
# import json
# import unicodedata
# from pathlib import Path
# from typing import Tuple, List, Dict, Any

# from bs4 import BeautifulSoup  # pip install beautifulsoup4

# from dd_agent.edgar.normalize import derived_dir
# from dd_agent.utils.io import ensure_dir


# # --- Patterns ---------------------------------------------------------------

# # Items to capture (10-K/10-Q)
# # Examples: "Item 1. Business", "ITEM 1A. RISK FACTORS", "Item 7A. Quantitative and Qualitative ..."
# ITEM_RX = re.compile(
#     r"(?im)^\s*item\s+("
#     r"1a?|1b|1c|2|3|4|5|6|7a?|8|9a?|9b|9c|1[0-6]"
#     r")\.\s*(.+?)\s*$"
# )

# # Start of the real body (to ignore TOC duplicates)
# PART_I_RX = re.compile(r"(?im)^\s*part\s+i\b")

# # Common page headers/footers like: "Apple Inc. | 2024 Form 10-K | 12"
# # This is purposefully generic: any line containing "Form 10-K" or "Form 10-Q" and a trailing number.
# FORM_HDR_RX = re.compile(r"(?i)^\s*.*\bForm\s+10-(K|Q)\b.*\b\d+\s*$")

# # Page-number only lines
# PAGE_NUM_ONLY_RX = re.compile(r"^\s*\d+\s*$")

# # Table of Contents block markers
# TOC_START_RX = re.compile(r"(?im)^\s*table\s+of\s+contents\s*$")
# # We cut TOC until PART I (or, if PART I not found, the first visible "Item 1.")
# # A soft fallback "Item 1" (line anchor) for edge cases:
# SOFT_ITEM1_RX = re.compile(r"(?im)^\s*item\s+1\.")


# # --- Helpers ----------------------------------------------------------------

# def _normalize_text(text: str) -> str:
#     # Unicode normalize + NBSP→space + collapse spaces + collapse excessive newlines
#     t = unicodedata.normalize("NFKC", text)
#     t = t.replace("\u00A0", " ")
#     t = re.sub(r"[ \t]+", " ", t)
#     t = re.sub(r"\n{3,}", "\n\n", t)
#     return t.strip()


# def _strip_toc_block(text: str) -> str:
#     """Remove Table of Contents block between TOC header and PART I (or first Item 1.)."""
#     toc = TOC_START_RX.search(text)
#     if not toc:
#         return text
#     body = PART_I_RX.search(text)
#     if not body:
#         body = SOFT_ITEM1_RX.search(text)
#     if body and toc.start() < body.start():
#         return text[:toc.start()] + text[body.start():]
#     return text


# def _strip_headers_footers(text: str) -> str:
#     """Remove page headers/footers and standalone page numbers."""
#     lines = text.splitlines()
#     out = []
#     for ln in lines:
#         if FORM_HDR_RX.match(ln):
#             continue
#         if PAGE_NUM_ONLY_RX.match(ln):
#             continue
#         out.append(ln)
#     return "\n".join(out)


# def _html_to_clean_text(html: str) -> str:
#     soup = BeautifulSoup(html, "lxml")  # lxml is faster/more robust; fallbacks to html.parser if unavailable
#     # Drop obvious non-content
#     for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
#         tag.decompose()
#     # Conservative text harvest: keep document order, respect block boundaries
#     text = soup.get_text("\n", strip=True)
#     text = _normalize_text(text)
#     # Remove TOC before section detection
#     text = _strip_toc_block(text)
#     # Remove running headers/footers after TOC cut
#     text = _strip_headers_footers(text)
#     # One more whitespace pass after removals
#     text = _normalize_text(text)
#     return text


# def _detect_items(text: str) -> List[Dict[str, Any]]:
#     """
#     Return list of {"label": "Item 1A", "title": "...", "start": int} for hits
#     that occur AFTER the start of PART I (body gate).
#     """
#     body_gate = PART_I_RX.search(text)
#     gate_pos = body_gate.start() if body_gate else 0

#     hits = []
#     for m in ITEM_RX.finditer(text):
#         if m.start() < gate_pos:
#             # Ignore TOC duplicates and preface occurrences
#             continue
#         code = m.group(1).upper()   # e.g., "1A", "7", "9B"
#         title = m.group(2).strip()
#         label = f"Item {code}"
#         hits.append({"label": label, "title": title, "start": m.start(), "match_len": m.end() - m.start()})

#     # Sort by start ascending
#     hits.sort(key=lambda d: d["start"])
#     return hits


# def _ranges_from_hits(text: str, hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     """
#     Build [start,end) ranges between successive item starts; then dedupe by label
#     keeping the longest span for any label that appears more than once.
#     """
#     if not hits:
#         return [{"label": "FULL", "title": "FULL", "start": 0, "end": len(text)}]

#     # First pass: naive contiguous ranges
#     ranges = []
#     for i, h in enumerate(hits):
#         start = h["start"]
#         end = hits[i + 1]["start"] if i + 1 < len(hits) else len(text)
#         ranges.append({
#             "label": h["label"],
#             "title": h["title"],
#             "start": start,
#             "end": end,
#             "span_len": end - start
#         })

#     # Deduplicate by keeping the longest span per label
#     best: Dict[str, Dict[str, Any]] = {}
#     for r in ranges:
#         key = r["label"]
#         if key not in best or r["span_len"] > best[key]["span_len"]:
#             best[key] = r

#     # Return in document order by start
#     out = sorted(best.values(), key=lambda d: d["start"])
#     for r in out:
#         r.pop("span_len", None)
#     return out


# def _assemble_markdown(text: str, sections: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
#     """
#     Build Markdown with '## Item … — Title' headings and compute new
#     start/end offsets relative to the assembled Markdown string.
#     """
#     md_parts: List[str] = []
#     idx: List[Dict[str, Any]] = []
#     cursor = 0

#     def _push(part: str):
#         nonlocal cursor
#         md_parts.append(part)
#         cursor += len(part)

#     for i, sec in enumerate(sections):
#         label = sec["label"]
#         title = sec["title"]
#         seg = text[sec["start"]:sec["end"]].strip()

#         # Heading
#         heading = f"## {label} — {title}\n\n"
#         start_char = cursor + len(heading)  # content starts after heading
#         _push(heading)

#         # Body (already normalized)
#         _push(seg + ("\n\n" if not seg.endswith("\n") else "\n"))

#         end_char = cursor  # after pushing seg + newline(s)

#         idx.append({
#             "section": label,
#             "title": title,
#             "start_char": start_char,
#             "end_char": end_char
#         })

#     md_text = "".join(md_parts).rstrip() + "\n"
#     return md_text, idx


# # --- Public API -------------------------------------------------------------

# def html_to_markdown_sectioned(
#     cik: str,
#     accession: str,
#     raw_primary_path: str | Path,
#     overwrite: bool,
#     config: dict,
# ) -> Tuple[Path, Path]:
#     """
#     Cleans HTML → Markdown; detects 10-K/10-Q Item sections; writes:
#       - derived/{cik}/{accession}/text/cleaned.md
#       - derived/{cik}/{accession}/sections/index.json
#     Index byte offsets align to the Markdown file.
#     """
#     out_root = derived_dir(config, cik, accession)
#     text_dir = ensure_dir(out_root / "text")
#     sec_dir = ensure_dir(out_root / "sections")
#     md_out = text_dir / "cleaned.md"
#     idx_out = sec_dir / "index.json"

#     if md_out.exists() and idx_out.exists() and not overwrite:
#         return md_out, idx_out

#     html = Path(raw_primary_path).read_text(encoding="utf-8", errors="ignore")
#     clean_text = _html_to_clean_text(html)

#     # Section detection
#     hits = _detect_items(clean_text)
#     ranges = _ranges_from_hits(clean_text, hits)

#     # Markdown assembly + index aligned to Markdown
#     md_text, md_index = _assemble_markdown(clean_text, ranges)

#     md_out.write_text(md_text, encoding="utf-8")
#     idx_out.write_text(json.dumps(md_index, ensure_ascii=False, indent=2), encoding="utf-8")
#     return md_out, idx_out


# src/dd_agent/edgar/parse_html.py
from __future__ import annotations
import re
import json
import unicodedata
from pathlib import Path
from typing import Tuple, List, Dict, Any
from shutil import rmtree

from bs4 import BeautifulSoup, FeatureNotFound, XMLParsedAsHTMLWarning
import warnings

# Optional: silence "XML parsed as HTML" noise if we end up parsing with HTML engine
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Optional dependency: pandas for table extraction
try:
    import pandas as pd
    from io import StringIO
    _HAS_PANDAS = True
except Exception:
    _HAS_PANDAS = False

from dd_agent.edgar.normalize import derived_dir
from dd_agent.utils.io import ensure_dir


# --- Patterns ---------------------------------------------------------------

# 10-K/10-Q items, case/spacing tolerant
ITEM_RX = re.compile(
    r"(?im)^\s*item\s+("
    r"1a?|1b|1c|2|3|4|5|6|7a?|8|9a?|9b|9c|1[0-6]"
    r")\.\s*(.+?)\s*$"
)

# Start of the main body; helps gate out TOC matches
PART_I_RX = re.compile(r"(?im)^\s*part\s+i\b")

# Running header/footer lines like: "Acme Inc. | 2024 Form 10-K | 12"
FORM_HDR_RX = re.compile(r"(?i)^\s*.*\bForm\s+10-(K|Q)\b.*\b\d+\s*$")

# Standalone page numbers
PAGE_NUM_ONLY_RX = re.compile(r"^\s*\d+\s*$")

# Table of Contents markers
TOC_START_RX = re.compile(r"(?im)^\s*table\s+of\s+contents\s*$")
SOFT_ITEM1_RX = re.compile(r"(?im)^\s*item\s+1\.")


# --- Parser helpers ---------------------------------------------------------

def _build_soup_auto(html: str) -> BeautifulSoup:
    """
    Prefer XML parser for obvious XML/Inline XBRL; otherwise use HTML parser.
    Tries parsers in order and returns the first that is available.
    """
    head = html.lstrip()[:400].lower()
    is_xmlish = head.startswith("<?xml") or any(tag in head for tag in ("<xbrl", "<xbrli:", "<ix:", "<inline", "<xml"))
    parsers = ("lxml-xml", "lxml") if is_xmlish else ("lxml", "html5lib", "html.parser")
    last_err = None
    for parser in parsers:
        try:
            return BeautifulSoup(html, parser)
        except FeatureNotFound as e:
            last_err = e
            continue
    # If we got here, no parser is available
    raise RuntimeError(
        f"No suitable HTML/XML parser available. Tried {parsers}. "
        f"Install 'lxml' (and optionally 'html5lib'). Last error: {last_err}"
    )


# --- Cleaning helpers -------------------------------------------------------

def _normalize_text(text: str) -> str:
    # Unicode normalize + NBSP→space + collapse spaces + collapse excessive newlines
    t = unicodedata.normalize("NFKC", text)
    t = t.replace("\u00A0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _strip_toc_block(text: str) -> str:
    """Remove Table of Contents block between TOC header and PART I (or first Item 1.)."""
    toc = TOC_START_RX.search(text)
    if not toc:
        return text
    body = PART_I_RX.search(text)
    if not body:
        body = SOFT_ITEM1_RX.search(text)
    if body and toc.start() < body.start():
        return text[:toc.start()] + text[body.start():]
    return text


def _strip_headers_footers(text: str) -> str:
    """Remove page headers/footers and standalone page numbers."""
    lines = text.splitlines()
    out = []
    for ln in lines:
        if FORM_HDR_RX.match(ln):
            continue
        if PAGE_NUM_ONLY_RX.match(ln):
            continue
        out.append(ln)
    return "\n".join(out)


# --- Table extraction --------------------------------------------------------

def _extract_tables_to_csv(soup: BeautifulSoup, tables_dir: Path) -> List[Dict[str, str]]:
    """
    Find <table> tags, render to CSVs (if pandas available), and replace each table
    with a text marker '[[TABLE:NN]]' so we can map tables back to positions
    in the plain-text later.

    Returns a list like:
      [{"file": "table_01.csv", "label": "Condensed Consolidated ...", "marker": "[[TABLE:01]]"}, ...]
    """
    tables_dir.mkdir(parents=True, exist_ok=True)
    out: List[Dict[str, str]] = []

    tables = list(soup.find_all("table"))
    for i, tbl in enumerate(tables, start=1):
        marker = f"[[TABLE:{i:02d}]]"
        name = f"table_{i:02d}.csv"
        path = tables_dir / name

        # Best-effort label
        label = None
        cap = tbl.find("caption")
        if cap:
            label = cap.get_text(strip=True)
        if not label:
            label = tbl.get("summary") or tbl.get("title")
        if not label:
            prev = tbl.find_previous(["h1", "h2", "h3", "h4"])
            if prev:
                label = prev.get_text(strip=True)
        if not label:
            label = "Table"

        # Extract to CSV (best-effort)
        if _HAS_PANDAS:
            try:
                from io import StringIO
                dfs = pd.read_html(StringIO(str(tbl)))
                if len(dfs) == 1:
                    dfs[0].to_csv(path, index=False)
                else:
                    sep = pd.DataFrame([[""] * max(d.shape[1] for d in dfs)])
                    merged = None
                    for d in dfs:
                        merged = d if merged is None else pd.concat([merged, sep, d], ignore_index=True)
                    (merged or dfs[0]).to_csv(path, index=False)
            except Exception:
                with path.open("w", encoding="utf-8") as f:
                    f.write("EXTRACTION_FAILED\n")
        else:
            with path.open("w", encoding="utf-8") as f:
                f.write("PANDAS_NOT_INSTALLED\n")

        # Replace table node with its marker so get_text() will include it
        tbl.replace_with(marker)

        out.append({"file": name, "label": label, "marker": marker})

    return out


# --- Section detection & markdown assembly ----------------------------------

def _detect_items(text: str) -> List[Dict[str, Any]]:
    """
    Return list of {"label": "Item 1A", "title": "...", "start": int} for hits
    that occur AFTER the start of PART I (body gate).
    """
    body_gate = PART_I_RX.search(text)
    gate_pos = body_gate.start() if body_gate else 0

    hits = []
    for m in ITEM_RX.finditer(text):
        if m.start() < gate_pos:
            continue  # ignore TOC and preface
        code = m.group(1).upper()   # e.g., "1A", "7", "9B"
        title = m.group(2).strip()
        label = f"Item {code}"
        hits.append({"label": label, "title": title, "start": m.start(), "match_len": m.end() - m.start()})

    hits.sort(key=lambda d: d["start"])
    return hits


def _ranges_from_hits(text: str, hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build [start,end) ranges between successive item starts; then dedupe by label
    keeping the longest span for any label that appears more than once.
    """
    if not hits:
        return [{"label": "FULL", "title": "FULL", "start": 0, "end": len(text)}]

    # First pass: contiguous ranges
    ranges = []
    for i, h in enumerate(hits):
        start = h["start"]
        end = hits[i + 1]["start"] if i + 1 < len(hits) else len(text)
        ranges.append({
            "label": h["label"],
            "title": h["title"],
            "start": start,
            "end": end,
            "span_len": end - start
        })

    # Deduplicate labels by longest span
    best: Dict[str, Dict[str, Any]] = {}
    for r in ranges:
        key = r["label"]
        if key not in best or r["span_len"] > best[key]["span_len"]:
            best[key] = r

    out = sorted(best.values(), key=lambda d: d["start"])
    for r in out:
        r.pop("span_len", None)
    return out


def _assemble_markdown(
    text: str,
    sections: List[Dict[str, Any]],
    per_section_tables: Dict[str, List[Dict[str, str]]],
    global_tables: List[Dict[str, str]],
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Build Markdown with '## Item … — Title', append a '### Tables' sublist
    under sections that have tables, and (if any remain) a global '## Tables'
    at the end. Returns (markdown_text, index_for_sections).
    """
    md_parts: List[str] = []
    idx: List[Dict[str, Any]] = []
    cursor = 0

    def _push(part: str):
        nonlocal cursor
        md_parts.append(part)
        cursor += len(part)

    for sec in sections:
        label = sec["label"]
        title = sec["title"]
        seg = text[sec["start"]:sec["end"]].strip()

        heading = f"## {label} — {title}\n\n"
        start_char = cursor + len(heading)
        _push(heading)
        _push(seg + ("\n\n" if not seg.endswith("\n") else "\n"))
        end_char = cursor

        # Per-section tables list (if any)
        tables_here = per_section_tables.get(label, [])
        if tables_here:
            _push("### Tables\n\n")
            for t in tables_here:
                _push(f"- [{t['label']}](/tables/{t['file']})\n")
            _push("\n")

        idx.append({
            "section": label,
            "title": title,
            "start_char": start_char,
            "end_char": end_char if not tables_here else cursor  # include tables block
        })

    # Global list for any leftover tables (not matched to a section)
    if global_tables:
        _push("## Tables\n\n")
        for t in global_tables:
            _push(f"- [{t['label']}](/tables/{t['file']})\n")
        _push("\n")

    md_text = "".join(md_parts).rstrip() + "\n"
    return md_text, idx


# --- Main cleaning pipeline --------------------------------------------------

def _html_to_clean_text_and_tables(html: str, tables_dir: Path) -> tuple[str, List[Dict[str, str]]]:
    """
    Parse HTML/XML, replace each table with a marker [[TABLE:NN]] and export CSVs.
    Then clean the text and locate each marker position; finally remove markers
    from the text but keep positions in tables_meta["pos"].
    """
    soup = _build_soup_auto(html)

    # Remove obvious non-content upfront
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()

    # Replace tables with markers and export CSVs
    tables_meta = _extract_tables_to_csv(soup, tables_dir=tables_dir)

    # Convert remaining soup to text (markers included)
    text = soup.get_text("\n", strip=True)
    text = _normalize_text(text)
    text = _strip_toc_block(text)
    text = _strip_headers_footers(text)
    text = _normalize_text(text)

    # Locate markers -> positions, then strip them from the text
    for t in tables_meta:
        m = t["marker"]
        pos = text.find(m)
        t["pos"] = pos  # -1 if not found (should be rare)
        if pos != -1:
            text = text.replace(m, "")  # remove marker from the final narrative

    return text, tables_meta



# --- Public API -------------------------------------------------------------

def html_to_markdown_sectioned(
    cik: str,
    accession: str,
    raw_primary_path: str | Path,
    overwrite: bool,
    config: dict,
) -> Tuple[Path, Path]:
    """
    Cleans HTML → Markdown; detects 10-K/10-Q Item sections; extracts tables to CSVs; writes:
      - derived/{cik}/{accession}/text/cleaned.md
      - derived/{cik}/{accession}/sections/index.json
      - derived/{cik}/{accession}/tables/table_XX.csv  (if any)
    Index byte offsets align to the Markdown file.
    """
    out_root = derived_dir(config, cik, accession)
    text_dir = ensure_dir(out_root / "text")
    sec_dir = ensure_dir(out_root / "sections")
    # Clean tables dir if forcing a rebuild, then recreate it
    tbl_dir = out_root / "tables"
    if overwrite and tbl_dir.exists():
        rmtree(tbl_dir, ignore_errors=True)
    tbl_dir = ensure_dir(tbl_dir)
    md_out = text_dir / "cleaned.md"
    idx_out = sec_dir / "index.json"

    if md_out.exists() and idx_out.exists() and not overwrite:
        return md_out, idx_out

    html = Path(raw_primary_path).read_text(encoding="utf-8", errors="ignore")
    clean_text, tables_meta = _html_to_clean_text_and_tables(html, tables_dir=tbl_dir)

    # Section detection
    hits = _detect_items(clean_text)
    ranges = _ranges_from_hits(clean_text, hits)

    # Build per-section table groups: compare table pos to section [start, end)
    per_section_tables: Dict[str, List[Dict[str, str]]] = {}
    leftover: List[Dict[str, str]] = []
    for t in tables_meta:
        pos = t.get("pos", -1)
        assigned = False
        if pos is not None and pos >= 0 and ranges:
            for r in ranges:
                if r["start"] <= pos < r["end"]:
                    per_section_tables.setdefault(r["label"], []).append(t)
                    assigned = True
                    break
        if not assigned:
            leftover.append(t)

    # Assemble Markdown and section index aligned to Markdown bytes
    md_text, md_index = _assemble_markdown(clean_text, ranges, per_section_tables, leftover)

    md_out.write_text(md_text, encoding="utf-8")
    idx_out.write_text(json.dumps(md_index, ensure_ascii=False, indent=2), encoding="utf-8")
    return md_out, idx_out
