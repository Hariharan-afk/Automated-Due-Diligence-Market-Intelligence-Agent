"""
Table-aware document chunking module for RAG.
Preserves semantic relationships between tables and surrounding context.
"""

import re
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib

from bs4 import BeautifulSoup

from .utils.logger import get_logger
from .utils.config import get_config

logger = get_logger("chunking")


@dataclass
class Table:
    """Represents an extracted table with metadata."""
    table_id: str
    position: int  # Character position in original text
    caption: str
    headers: List[str]
    data: List[List[str]]  # Rows of data
    html: str  # Original HTML
    markdown: str  # Markdown representation
    num_rows: int
    num_cols: int


@dataclass
class DocumentChunk:
    """A chunk of document with metadata for RAG retrieval."""
    chunk_id: str
    text: str
    metadata: Dict
    token_count: int
    chunk_index: int
    has_table: bool = False
    table_id: Optional[str] = None
    references_chunks: List[str] = None  # IDs of related chunks

    def __post_init__(self):
        if self.references_chunks is None:
            self.references_chunks = []

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return asdict(self)


class TableExtractor:
    """Extracts tables from HTML or text content (SEC filings)."""

    def __init__(self):
        self.logger = get_logger("table_extractor")

    def extract_tables_from_text(self, text_content: str, marker_start: str = "##TABLE_START", marker_end: str = "##TABLE_END") -> List[Table]:
        """
        Extract tables from text content with markers (e.g., SEC filings).

        Args:
            text_content: Text content with table markers
            marker_start: Opening table marker (default: ##TABLE_START)
            marker_end: Closing table marker (default: ##TABLE_END)

        Returns:
            List of Table objects
        """
        try:
            tables = []

            # Find all tables using markers
            pattern = re.escape(marker_start) + r'(.*?)' + re.escape(marker_end)
            matches = re.findall(pattern, text_content, re.DOTALL)

            for idx, table_text in enumerate(matches):
                table_obj = self._parse_text_table(table_text.strip(), idx)
                if table_obj:
                    # Store position for context extraction
                    start_pos = text_content.find(marker_start + table_text)
                    table_obj.position = start_pos
                    tables.append(table_obj)

            self.logger.info(f"Extracted {len(tables)} tables from text content")
            return tables

        except Exception as e:
            self.logger.error(f"Failed to extract tables from text: {e}")
            return []

    def _parse_text_table(self, table_text: str, idx: int) -> Optional[Table]:
        """
        Parse text-based table into structured format.

        Tables in SEC filings are space/whitespace-separated.
        First line typically contains headers.
        """
        try:
            lines = [line.strip() for line in table_text.split('\n') if line.strip()]

            if not lines:
                return None

            # First line as headers (split by multiple spaces or tabs)
            header_line = lines[0]
            headers = re.split(r'\s{2,}|\t', header_line)
            headers = [h.strip() for h in headers if h.strip()]

            # Remaining lines as data
            data = []
            for line in lines[1:]:
                # Split by multiple spaces (2+) to separate columns
                row = re.split(r'\s{2,}', line)
                row = [cell.strip() for cell in row if cell.strip()]
                if row:
                    data.append(row)

            if not data:
                # No data rows, skip
                return None

            # Generate caption from context or use generic
            caption = f"Table {idx + 1}"

            # Generate table ID
            table_content = f"{caption}{''.join(headers)}{''.join(str(r) for r in data)}"
            table_id = hashlib.md5(table_content.encode()).hexdigest()[:12]

            # Convert to markdown
            markdown = self._table_to_markdown(caption, headers, data)

            table = Table(
                table_id=table_id,
                position=0,  # Will be set by caller
                caption=caption,
                headers=headers,
                data=data,
                html="",  # No HTML for text tables
                markdown=markdown,
                num_rows=len(data),
                num_cols=len(headers) if headers else (len(data[0]) if data else 0)
            )

            return table

        except Exception as e:
            self.logger.warning(f"Failed to parse text table: {e}")
            return None

    def extract_tables_from_html(self, html_content: str) -> List[Table]:
        """
        Extract tables from HTML content.

        Args:
            html_content: HTML string

        Returns:
            List of Table objects
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            tables = []

            for idx, table_tag in enumerate(soup.find_all('table')):
                table_obj = self._parse_table_tag(table_tag, idx)
                if table_obj:
                    tables.append(table_obj)

            self.logger.info(f"Extracted {len(tables)} tables from HTML")
            return tables

        except Exception as e:
            self.logger.error(f"Failed to extract tables: {e}")
            return []

    def _parse_table_tag(self, table_tag, idx: int) -> Optional[Table]:
        """Parse a single HTML table tag."""
        try:
            # Get caption if exists
            caption_tag = table_tag.find('caption')
            caption = caption_tag.get_text(strip=True) if caption_tag else f"Table {idx + 1}"

            # Extract headers
            headers = []
            header_row = table_tag.find('thead')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            else:
                # Try first row if no thead
                first_row = table_tag.find('tr')
                if first_row:
                    headers = [th.get_text(strip=True) for th in first_row.find_all(['th', 'td'])]

            # Extract data rows
            rows = []
            tbody = table_tag.find('tbody') or table_tag
            for tr in tbody.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if cells and cells != headers:  # Skip header row if in tbody
                    rows.append(cells)

            if not rows:
                return None

            # Generate table ID
            table_content = f"{caption}{''.join(headers)}{''.join(str(r) for r in rows)}"
            table_id = hashlib.md5(table_content.encode()).hexdigest()[:12]

            # Convert to markdown
            markdown = self._table_to_markdown(caption, headers, rows)

            # Get HTML string
            html = str(table_tag)

            # Calculate position (approximate)
            position = 0  # Will be set by caller

            table = Table(
                table_id=table_id,
                position=position,
                caption=caption,
                headers=headers,
                data=rows,
                html=html,
                markdown=markdown,
                num_rows=len(rows),
                num_cols=len(headers) if headers else (len(rows[0]) if rows else 0)
            )

            return table

        except Exception as e:
            self.logger.warning(f"Failed to parse table: {e}")
            return None

    def _table_to_markdown(self, caption: str, headers: List[str], rows: List[List[str]]) -> str:
        """Convert table to markdown format."""
        lines = []

        # Caption
        if caption:
            lines.append(f"**{caption}**\n")

        # Headers
        if headers:
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # Rows
        for row in rows:
            # Pad row to match header length if needed
            if headers and len(row) < len(headers):
                row = row + [""] * (len(headers) - len(row))
            elif headers and len(row) > len(headers):
                row = row[:len(headers)]

            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")

        return "\n".join(lines)


class TokenEstimator:
    """Estimates token counts for text."""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate token count using simple heuristic.
        Rough approximation: ~4 characters per token for English.

        Args:
            text: Text string

        Returns:
            Estimated token count
        """
        # Simple heuristic: count words and punctuation
        words = len(text.split())
        # Add some overhead for special tokens
        return int(words * 1.3)


class DocumentChunker:
    """
    Intelligent document chunker with table-awareness.
    Preserves semantic relationships between tables and surrounding text.
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
        preserve_tables: Optional[bool] = None,
        table_context_paragraphs: Optional[int] = None
    ):
        """
        Initialize document chunker.

        Args:
            chunk_size: Maximum tokens per chunk
            overlap: Token overlap between chunks
            preserve_tables: Whether to preserve table-text relationships
            table_context_paragraphs: Number of paragraphs to include before/after table
        """
        self.config = get_config()

        # Load config or use defaults
        self.chunk_size = chunk_size or self.config.chunking.chunk_size
        self.overlap = overlap or self.config.chunking.overlap
        self.preserve_tables = preserve_tables if preserve_tables is not None else self.config.chunking.preserve_tables
        self.table_context_paragraphs = table_context_paragraphs or self.config.chunking.table_context_paragraphs

        self.table_extractor = TableExtractor()
        self.token_estimator = TokenEstimator()

        logger.info(f"Chunker initialized: size={self.chunk_size}, overlap={self.overlap}, preserve_tables={self.preserve_tables}")

    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict] = None,
        source_type: str = "text"
    ) -> List[DocumentChunk]:
        """
        Chunk text with optional table awareness.

        Args:
            text: Text to chunk
            metadata: Base metadata for chunks
            source_type: Type of source (text, html, sec_filing, etc.)

        Returns:
            List of DocumentChunk objects
        """
        metadata = metadata or {}

        # Route to appropriate chunking strategy based on source type
        if self.preserve_tables:
            # SEC filings: text-based tables with markers
            if source_type == "sec_filing":
                return self._chunk_sec_filing_text(text, metadata)
            # HTML content: HTML tables
            elif source_type == "html" or "<table" in text.lower():
                return self._chunk_with_tables(text, metadata)

        # Simple text chunking (no tables or tables not preserved)
        return self._chunk_text_only(text, metadata)

    def _chunk_text_only(self, text: str, metadata: Dict) -> List[DocumentChunk]:
        """
        Simple text chunking without table awareness.

        Strategy:
        1. Split by paragraphs (preserve paragraph boundaries)
        2. Combine paragraphs into chunks up to chunk_size
        3. Add overlap between chunks
        """
        chunks = []

        # Split into paragraphs
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        current_chunk = []
        current_tokens = 0
        chunk_idx = 0

        for para in paragraphs:
            para_tokens = self.token_estimator.estimate_tokens(para)

            # If single paragraph exceeds chunk size, split it
            if para_tokens > self.chunk_size:
                # Save current chunk if any
                if current_chunk:
                    chunks.append(self._create_chunk(
                        "\n\n".join(current_chunk),
                        metadata,
                        chunk_idx
                    ))
                    chunk_idx += 1
                    current_chunk = []
                    current_tokens = 0

                # Split large paragraph by sentences
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sentence in sentences:
                    sentence_tokens = self.token_estimator.estimate_tokens(sentence)

                    if current_tokens + sentence_tokens > self.chunk_size:
                        if current_chunk:
                            chunks.append(self._create_chunk(
                                "\n\n".join(current_chunk),
                                metadata,
                                chunk_idx
                            ))
                            chunk_idx += 1

                        # Start new chunk with overlap
                        current_chunk = [sentence]
                        current_tokens = sentence_tokens
                    else:
                        current_chunk.append(sentence)
                        current_tokens += sentence_tokens

            # Add paragraph to current chunk
            elif current_tokens + para_tokens <= self.chunk_size:
                current_chunk.append(para)
                current_tokens += para_tokens
            else:
                # Save current chunk
                chunks.append(self._create_chunk(
                    "\n\n".join(current_chunk),
                    metadata,
                    chunk_idx
                ))
                chunk_idx += 1

                # Start new chunk with overlap
                overlap_text = current_chunk[-1] if current_chunk else ""
                current_chunk = [overlap_text, para] if overlap_text else [para]
                current_tokens = self.token_estimator.estimate_tokens("\n\n".join(current_chunk))

        # Add final chunk
        if current_chunk:
            chunks.append(self._create_chunk(
                "\n\n".join(current_chunk),
                metadata,
                chunk_idx
            ))

        logger.info(f"Created {len(chunks)} text-only chunks")
        return chunks

    def _chunk_sec_filing_text(self, text: str, metadata: Dict) -> List[DocumentChunk]:
        """
        Table-aware chunking for SEC filings with ##TABLE_START/##TABLE_END markers.

        Strategy:
        1. Extract tables from text using markers
        2. For each table, get surrounding context (paragraphs before/after)
        3. Create chunks that include table + context together
        4. If table+context is too large, split intelligently
        5. Create cross-references between related chunks
        """
        chunks = []

        # Extract tables with markers
        tables = self.table_extractor.extract_tables_from_text(text)

        if not tables:
            # No tables found, fall back to regular chunking
            return self._chunk_text_only(text, metadata)

        # Remove table markers from text and replace with placeholders
        text_with_placeholders = text
        table_map = {}

        for idx, table in enumerate(tables):
            placeholder = f"[[TABLE_{idx}]]"
            table_map[placeholder] = table

            # Find and replace table in text (including markers)
            # Pattern: ##TABLE_START...##TABLE_END
            pattern = r'##TABLE_START.*?##TABLE_END'
            # Replace only the first occurrence (tables are in order)
            text_with_placeholders = re.sub(
                pattern,
                placeholder,
                text_with_placeholders,
                count=1,
                flags=re.DOTALL
            )

        # Split into segments (text, table, text, table, ...)
        segments = []
        current_text = ""

        for line in text_with_placeholders.split('\n'):
            if '[[TABLE_' in line:
                # Found table placeholder
                if current_text.strip():
                    segments.append(('text', current_text.strip()))
                    current_text = ""

                # Extract table index
                match = re.search(r'\[\[TABLE_(\d+)\]\]', line)
                if match:
                    table_idx = int(match.group(1))
                    placeholder = f"[[TABLE_{table_idx}]]"
                    if placeholder in table_map:
                        segments.append(('table', table_map[placeholder]))
            else:
                current_text += line + "\n"

        # Add remaining text
        if current_text.strip():
            segments.append(('text', current_text.strip()))

        # Create chunks from segments
        chunk_idx = 0
        i = 0

        while i < len(segments):
            seg_type, seg_content = segments[i]

            if seg_type == 'table':
                # Create table-aware chunk
                table = seg_content

                # Get context before table
                context_before = []
                j = i - 1
                while j >= 0 and len(context_before) < self.table_context_paragraphs:
                    if segments[j][0] == 'text':
                        paragraphs = re.split(r'\n\s*\n', segments[j][1])
                        # Get last N paragraphs
                        context_before = paragraphs[-self.table_context_paragraphs:] + context_before
                        break
                    j -= 1

                # Get context after table
                context_after = []
                j = i + 1
                while j < len(segments) and len(context_after) < self.table_context_paragraphs:
                    if segments[j][0] == 'text':
                        paragraphs = re.split(r'\n\s*\n', segments[j][1])
                        # Get first N paragraphs
                        context_after = paragraphs[:self.table_context_paragraphs]
                        break
                    j += 1

                # Combine context + table
                chunk_text_parts = []
                if context_before:
                    chunk_text_parts.append("\n\n".join(context_before))

                chunk_text_parts.append(f"\n\n{table.markdown}\n\n")

                if context_after:
                    chunk_text_parts.append("\n\n".join(context_after))

                chunk_text = "".join(chunk_text_parts)
                tokens = self.token_estimator.estimate_tokens(chunk_text)

                # Check if chunk fits in size limit
                if tokens <= self.chunk_size:
                    # Single chunk with table + context
                    chunk_meta = {
                        **metadata,
                        "has_table": True,
                        "table_id": table.table_id,
                        "table_caption": table.caption,
                        "table_rows": table.num_rows,
                        "table_cols": table.num_cols
                    }

                    chunk = self._create_chunk(chunk_text, chunk_meta, chunk_idx, has_table=True, table_id=table.table_id)
                    chunks.append(chunk)
                    chunk_idx += 1

                else:
                    # Table + context too large, split into:
                    # 1. Context chunk with table reference
                    # 2. Table chunk with context reference

                    # Context chunk
                    context_text = "\n\n".join(context_before + context_after)
                    if context_text:
                        context_chunk = self._create_chunk(
                            context_text + f"\n\n[Refer to Table: {table.caption}]",
                            {**metadata, "references_table": table.table_id, "table_caption": table.caption},
                            chunk_idx
                        )
                        chunks.append(context_chunk)
                        chunk_idx += 1

                    # Table chunk
                    table_chunk = self._create_chunk(
                        table.markdown,
                        {
                            **metadata,
                            "is_table": True,
                            "table_id": table.table_id,
                            "table_caption": table.caption,
                            "table_rows": table.num_rows,
                            "table_cols": table.num_cols
                        },
                        chunk_idx,
                        has_table=True,
                        table_id=table.table_id
                    )

                    # Cross-reference
                    if chunks:
                        table_chunk.references_chunks.append(chunks[-1].chunk_id)
                        chunks[-1].references_chunks.append(table_chunk.chunk_id)

                    chunks.append(table_chunk)
                    chunk_idx += 1

                i += 1

            elif seg_type == 'text':
                # Regular text segment, use standard chunking
                text_chunks = self._chunk_text_only(seg_content, metadata)

                # Update chunk indices
                for tc in text_chunks:
                    tc.chunk_index = chunk_idx
                    tc.chunk_id = f"chunk_{chunk_idx}_{tc.chunk_id.split('_')[-1]}"
                    chunks.append(tc)
                    chunk_idx += 1

                i += 1

        logger.info(f"Created {len(chunks)} SEC filing chunks ({len(tables)} tables)")
        return chunks

    def _chunk_with_tables(self, html_text: str, metadata: Dict) -> List[DocumentChunk]:
        """
        Table-aware chunking that preserves table-text relationships.

        Strategy:
        1. Extract tables from HTML
        2. For each table, get surrounding context (paragraphs before/after)
        3. Create chunks that include table + context together
        4. If table+context is too large, split intelligently
        5. Create cross-references between related chunks
        """
        chunks = []

        # Extract tables
        tables = self.table_extractor.extract_tables_from_html(html_text)

        if not tables:
            # No tables found, fall back to regular chunking
            # Strip HTML tags first
            text_only = BeautifulSoup(html_text, 'html.parser').get_text()
            return self._chunk_text_only(text_only, metadata)

        # Convert HTML to text but keep track of table positions
        soup = BeautifulSoup(html_text, 'html.parser')

        # Replace tables with placeholders
        table_map = {}
        for idx, table in enumerate(tables):
            placeholder = f"[[TABLE_{idx}]]"
            table_map[placeholder] = table

            # Find original table in soup and replace
            for table_tag in soup.find_all('table'):
                if str(table_tag) == table.html:
                    table_tag.replace_with(placeholder)
                    break

        # Get text with placeholders
        text_with_placeholders = soup.get_text()

        # Split into segments (before table, table, after table, ...)
        segments = []
        current_text = ""

        for line in text_with_placeholders.split('\n'):
            if '[[TABLE_' in line:
                # Found table placeholder
                if current_text.strip():
                    segments.append(('text', current_text.strip()))
                    current_text = ""

                # Extract table index
                match = re.search(r'\[\[TABLE_(\d+)\]\]', line)
                if match:
                    table_idx = int(match.group(1))
                    placeholder = f"[[TABLE_{table_idx}]]"
                    if placeholder in table_map:
                        segments.append(('table', table_map[placeholder]))
            else:
                current_text += line + "\n"

        # Add remaining text
        if current_text.strip():
            segments.append(('text', current_text.strip()))

        # Now create chunks from segments
        chunk_idx = 0
        i = 0

        while i < len(segments):
            seg_type, seg_content = segments[i]

            if seg_type == 'table':
                # Create table-aware chunk
                table = seg_content

                # Get context before table
                context_before = []
                j = i - 1
                while j >= 0 and len(context_before) < self.table_context_paragraphs:
                    if segments[j][0] == 'text':
                        paragraphs = re.split(r'\n\s*\n', segments[j][1])
                        context_before = paragraphs[-self.table_context_paragraphs:] + context_before
                        break
                    j -= 1

                # Get context after table
                context_after = []
                j = i + 1
                while j < len(segments) and len(context_after) < self.table_context_paragraphs:
                    if segments[j][0] == 'text':
                        paragraphs = re.split(r'\n\s*\n', segments[j][1])
                        context_after = paragraphs[:self.table_context_paragraphs]
                        break
                    j += 1

                # Combine context + table
                chunk_text_parts = []
                if context_before:
                    chunk_text_parts.append("\n\n".join(context_before))

                chunk_text_parts.append(f"\n\n{table.markdown}\n\n")

                if context_after:
                    chunk_text_parts.append("\n\n".join(context_after))

                chunk_text = "".join(chunk_text_parts)
                tokens = self.token_estimator.estimate_tokens(chunk_text)

                # Check if chunk fits in size limit
                if tokens <= self.chunk_size:
                    # Single chunk with table + context
                    chunk_meta = {
                        **metadata,
                        "has_table": True,
                        "table_id": table.table_id,
                        "table_caption": table.caption,
                        "table_rows": table.num_rows,
                        "table_cols": table.num_cols
                    }

                    chunk = self._create_chunk(chunk_text, chunk_meta, chunk_idx, has_table=True, table_id=table.table_id)
                    chunks.append(chunk)
                    chunk_idx += 1

                else:
                    # Table + context too large, split into:
                    # 1. Context chunk with table reference
                    # 2. Table chunk with context reference

                    # Context chunk
                    context_text = "\n\n".join(context_before + context_after)
                    if context_text:
                        context_chunk = self._create_chunk(
                            context_text + f"\n\n[Refer to Table: {table.caption}]",
                            {**metadata, "references_table": table.table_id, "table_caption": table.caption},
                            chunk_idx
                        )
                        chunks.append(context_chunk)
                        chunk_idx += 1

                    # Table chunk
                    table_chunk = self._create_chunk(
                        table.markdown,
                        {
                            **metadata,
                            "is_table": True,
                            "table_id": table.table_id,
                            "table_caption": table.caption,
                            "table_rows": table.num_rows,
                            "table_cols": table.num_cols
                        },
                        chunk_idx,
                        has_table=True,
                        table_id=table.table_id
                    )

                    # Cross-reference
                    if chunks:
                        table_chunk.references_chunks.append(chunks[-1].chunk_id)
                        chunks[-1].references_chunks.append(table_chunk.chunk_id)

                    chunks.append(table_chunk)
                    chunk_idx += 1

                i += 1

            elif seg_type == 'text':
                # Regular text segment, use standard chunking
                text_chunks = self._chunk_text_only(seg_content, metadata)

                # Update chunk indices
                for tc in text_chunks:
                    tc.chunk_index = chunk_idx
                    tc.chunk_id = f"chunk_{chunk_idx}_{tc.chunk_id.split('_')[-1]}"
                    chunks.append(tc)
                    chunk_idx += 1

                i += 1

        logger.info(f"Created {len(chunks)} table-aware chunks ({len(tables)} tables)")
        return chunks

    def _create_chunk(
        self,
        text: str,
        metadata: Dict,
        chunk_idx: int,
        has_table: bool = False,
        table_id: Optional[str] = None
    ) -> DocumentChunk:
        """Create a DocumentChunk object."""
        # Generate chunk ID
        chunk_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        chunk_id = f"chunk_{chunk_idx}_{chunk_hash}"

        # Estimate tokens
        tokens = self.token_estimator.estimate_tokens(text)

        chunk = DocumentChunk(
            chunk_id=chunk_id,
            text=text,
            metadata=metadata.copy(),
            token_count=tokens,
            chunk_index=chunk_idx,
            has_table=has_table,
            table_id=table_id
        )

        return chunk

    def save_chunks(self, chunks: List[DocumentChunk], output_path: Path):
        """
        Save chunks to JSON file.

        Args:
            chunks: List of chunks
            output_path: Output file path
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            chunks_data = [chunk.to_dict() for chunk in chunks]

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(chunks_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved {len(chunks)} chunks to {output_path}")

        except Exception as e:
            logger.error(f"Failed to save chunks: {e}")


# Example usage
if __name__ == "__main__":
    # Initialize chunker
    chunker = DocumentChunker(chunk_size=500, overlap=50, preserve_tables=True)

    print("=" * 80)
    print("EXAMPLE 1: HTML Table Chunking (Wikipedia/News)")
    print("=" * 80)

    # Example HTML with tables
    html_content = """
    <html>
    <body>
        <p>Our company showed strong growth in Q4 2024.</p>

        <table>
            <caption>Quarterly Revenue</caption>
            <thead>
                <tr><th>Quarter</th><th>Revenue (M)</th><th>Growth</th></tr>
            </thead>
            <tbody>
                <tr><td>Q1</td><td>$100</td><td>10%</td></tr>
                <tr><td>Q2</td><td>$110</td><td>10%</td></tr>
                <tr><td>Q3</td><td>$125</td><td>14%</td></tr>
                <tr><td>Q4</td><td>$150</td><td>20%</td></tr>
            </tbody>
        </table>

        <p>The growth was primarily driven by strong iPhone sales.</p>
    </body>
    </html>
    """

    # Chunk with table awareness
    html_chunks = chunker.chunk_text(
        html_content,
        metadata={"source": "wikipedia", "company": "TestCorp"},
        source_type="html"
    )

    print(f"\nCreated {len(html_chunks)} chunks from HTML:")
    for chunk in html_chunks:
        print(f"\n--- Chunk {chunk.chunk_index} (ID: {chunk.chunk_id}) ---")
        print(f"Tokens: {chunk.token_count}")
        print(f"Has Table: {chunk.has_table}")
        if chunk.has_table:
            print(f"Table ID: {chunk.table_id}")
        print(f"Text preview: {chunk.text[:200]}...")

    print("\n" + "=" * 80)
    print("EXAMPLE 2: SEC Filing Text Table Chunking")
    print("=" * 80)

    # Example SEC filing text with table markers (actual format from sec-api.io)
    sec_content = """
Net sales by reportable segment for 2024, 2023 and 2022 were as follows (in millions):

##TABLE_START
2024  Change  2023  Change  2022
Americas  $ 167,045  3 %  $ 162,560  (4) %  $ 169,658
Europe  101,328  7 %  94,294  (1) %  95,118
Greater China  66,952  (8) %  72,559  (2) %  74,200
Japan  25,303  10 %  23,021  (7) %  24,840
Rest of Asia Pacific  30,308  4 %  29,205  1 %  28,936
Total net sales  $ 390,936  2 %  $ 381,639  (3) %  $ 392,752
##TABLE_END

The Americas segment includes North and South America. The Europe segment includes European countries, as well as India, the Middle East and Africa. The Greater China segment includes China mainland, Hong Kong and Taiwan.

Management's Discussion and Analysis of Financial Condition and Results of Operations follows this table.
    """

    # Chunk SEC filing with text-based tables
    sec_chunks = chunker.chunk_text(
        sec_content,
        metadata={"source": "sec_filing", "company": "Apple Inc", "filing_type": "10-K", "section": "Item 8"},
        source_type="sec_filing"
    )

    print(f"\nCreated {len(sec_chunks)} chunks from SEC filing:")
    for chunk in sec_chunks:
        print(f"\n--- Chunk {chunk.chunk_index} (ID: {chunk.chunk_id}) ---")
        print(f"Tokens: {chunk.token_count}")
        print(f"Has Table: {chunk.has_table}")
        if chunk.has_table:
            print(f"Table ID: {chunk.table_id}")
            print(f"Table Rows: {chunk.metadata.get('table_rows', 'N/A')}")
            print(f"Table Cols: {chunk.metadata.get('table_cols', 'N/A')}")
        print(f"Text preview:\n{chunk.text[:300]}...")
