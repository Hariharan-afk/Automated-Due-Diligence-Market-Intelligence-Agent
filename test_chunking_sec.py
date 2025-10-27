"""
Standalone test script for SEC filing table-aware chunking.
Tests the text-based table extraction with ##TABLE_START/##TABLE_END markers.
"""

import re
import hashlib
from typing import List, Dict, Optional
from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass
class Table:
    """Represents an extracted table with metadata."""
    table_id: str
    position: int
    caption: str
    headers: List[str]
    data: List[List[str]]
    html: str
    markdown: str
    num_rows: int
    num_cols: int


class TableExtractor:
    """Extracts tables from text content (SEC filings)."""

    def extract_tables_from_text(self, text_content: str, marker_start: str = "##TABLE_START", marker_end: str = "##TABLE_END") -> List[Table]:
        """Extract tables from text content with markers."""
        try:
            tables = []
            pattern = re.escape(marker_start) + r'(.*?)' + re.escape(marker_end)
            matches = re.findall(pattern, text_content, re.DOTALL)

            for idx, table_text in enumerate(matches):
                table_obj = self._parse_text_table(table_text.strip(), idx)
                if table_obj:
                    start_pos = text_content.find(marker_start + table_text)
                    table_obj.position = start_pos
                    tables.append(table_obj)

            print(f"[OK] Extracted {len(tables)} tables from text content")
            return tables

        except Exception as e:
            print(f"[ERROR] Failed to extract tables: {e}")
            return []

    def _parse_text_table(self, table_text: str, idx: int) -> Optional[Table]:
        """Parse text-based table into structured format."""
        try:
            lines = [line.strip() for line in table_text.split('\n') if line.strip()]

            if not lines:
                return None

            # First line as headers
            header_line = lines[0]
            headers = re.split(r'\s{2,}|\t', header_line)
            headers = [h.strip() for h in headers if h.strip()]

            # Remaining lines as data
            data = []
            for line in lines[1:]:
                row = re.split(r'\s{2,}', line)
                row = [cell.strip() for cell in row if cell.strip()]
                if row:
                    data.append(row)

            if not data:
                return None

            caption = f"Table {idx + 1}"
            table_content = f"{caption}{''.join(headers)}{''.join(str(r) for r in data)}"
            table_id = hashlib.md5(table_content.encode()).hexdigest()[:12]

            # Convert to markdown
            markdown = self._table_to_markdown(caption, headers, data)

            table = Table(
                table_id=table_id,
                position=0,
                caption=caption,
                headers=headers,
                data=data,
                html="",
                markdown=markdown,
                num_rows=len(data),
                num_cols=len(headers) if headers else (len(data[0]) if data else 0)
            )

            return table

        except Exception as e:
            print(f"[ERROR] Failed to parse table: {e}")
            return None

    def _table_to_markdown(self, caption: str, headers: List[str], rows: List[List[str]]) -> str:
        """Convert table to markdown format."""
        lines = []

        if caption:
            lines.append(f"**{caption}**\n")

        if headers:
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        for row in rows:
            if headers and len(row) < len(headers):
                row = row + [""] * (len(headers) - len(row))
            elif headers and len(row) > len(headers):
                row = row[:len(headers)]
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")

        return "\n".join(lines)


def test_sec_table_extraction():
    """Test SEC filing table extraction."""
    print("\n" + "=" * 80)
    print("Testing SEC Filing Table Extraction")
    print("=" * 80 + "\n")

    # Real SEC filing example (Apple 10-K format)
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

The Americas segment includes North and South America. The Europe segment includes European countries, as well as India, the Middle East and Africa.
    """

    # Test extraction
    extractor = TableExtractor()
    tables = extractor.extract_tables_from_text(sec_content)

    if not tables:
        print("[FAIL] No tables extracted!")
        return False

    print(f"\n[SUCCESS] Extracted {len(tables)} table(s)\n")

    # Verify table structure
    for table in tables:
        print(f"Table ID: {table.table_id}")
        print(f"Caption: {table.caption}")
        print(f"Dimensions: {table.num_rows} rows × {table.num_cols} columns")
        print(f"Headers: {table.headers}")
        print(f"\nMarkdown Output:\n{'-' * 40}")
        print(table.markdown)
        print('-' * 40)

        # Verify data integrity
        print(f"\nData Rows ({len(table.data)}):")
        for i, row in enumerate(table.data, 1):
            print(f"  Row {i}: {row}")

    # Verification checks
    checks = [
        (len(tables) == 1, "Exactly 1 table extracted"),
        (tables[0].num_cols == 5, "Table has 5 columns (2024, Change, 2023, Change, 2022)"),
        (tables[0].num_rows == 6, "Table has 6 data rows (5 segments + total)"),
        ("Americas" in str(tables[0].data), "Contains 'Americas' row"),
        ("$ 167,045" in str(tables[0].data), "Contains revenue data"),
    ]

    print("\n" + "=" * 80)
    print("Verification Checks:")
    print("=" * 80)

    all_passed = True
    for passed, description in checks:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {description}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED!")
        print("=" * 80 + "\n")
    else:
        print("\n" + "=" * 80)
        print("SOME TESTS FAILED!")
        print("=" * 80 + "\n")

    return all_passed


if __name__ == "__main__":
    test_sec_table_extraction()
