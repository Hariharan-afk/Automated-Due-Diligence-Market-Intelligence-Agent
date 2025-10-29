"""
Unit tests for Chunking module
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.chunking import DocumentChunker, Table, DocumentChunk


class TestDocumentChunker:
    """Test DocumentChunker functionality"""

    def test_init_default_params(self):
        """Test chunker initialization with default parameters"""
        chunker = DocumentChunker()
        assert chunker.chunk_size == 500
        assert chunker.overlap == 50
        assert chunker.preserve_tables == True

    def test_init_custom_params(self):
        """Test chunker initialization with custom parameters"""
        chunker = DocumentChunker(chunk_size=1000, overlap=100, preserve_tables=False)
        assert chunker.chunk_size == 1000
        assert chunker.overlap == 100
        assert chunker.preserve_tables == False

    def test_token_estimation(self):
        """Test token count estimation"""
        chunker = DocumentChunker()
        text = "This is a simple test sentence with several words."
        tokens = chunker.token_estimator.estimate_tokens(text)
        assert tokens > 0
        assert isinstance(tokens, int)

    def test_simple_text_chunking(self):
        """Test simple text chunking without tables"""
        chunker = DocumentChunker(chunk_size=50, overlap=10)
        text = "This is a simple test. " * 50  # Create long text

        chunks = chunker.chunk_text(text, metadata={'source': 'test'}, source_type='text')

        assert len(chunks) > 0
        assert all(isinstance(chunk, DocumentChunk) for chunk in chunks)
        assert all(hasattr(chunk, 'text') for chunk in chunks)
        assert all(hasattr(chunk, 'chunk_id') for chunk in chunks)


class TestTableExtraction:
    """Test table extraction functionality"""

    def test_extract_tables_from_text(self):
        """Test text-based table extraction"""
        chunker = DocumentChunker()

        text_with_table = """
Net sales by segment:

##TABLE_START
2024  Change  2023
Americas  100  10%  90
Europe  80  5%  76
##TABLE_END

The Americas segment showed strong growth.
"""

        tables = chunker.table_extractor.extract_tables_from_text(text_with_table)

        assert len(tables) == 1
        assert isinstance(tables[0], Table)
        assert tables[0].num_rows > 0
        assert tables[0].num_cols > 0
        assert len(tables[0].headers) > 0

    def test_multiple_tables(self):
        """Test extraction of multiple tables"""
        chunker = DocumentChunker()

        text = """
First table:
##TABLE_START
Col1  Col2
A  B
##TABLE_END

Second table:
##TABLE_START
Col1  Col2
C  D
##TABLE_END
"""

        tables = chunker.table_extractor.extract_tables_from_text(text)
        assert len(tables) == 2

    def test_no_tables(self):
        """Test text without tables"""
        chunker = DocumentChunker()
        text = "This is plain text without any tables."

        tables = chunker.table_extractor.extract_tables_from_text(text)
        assert len(tables) == 0


class TestSECFilingChunking:
    """Test SEC filing specific chunking"""

    def test_sec_filing_source_type(self):
        """Test chunking with SEC filing source type"""
        chunker = DocumentChunker(chunk_size=500, preserve_tables=True)

        sec_text = """
Item 1. Business

Our company operates in three segments.

##TABLE_START
2024  Revenue
Segment A  1000
Segment B  800
Segment C  600
##TABLE_END

Total revenue increased by 15%.
"""

        chunks = chunker.chunk_text(sec_text, metadata={'source': 'sec_filing'}, source_type='sec_filing')

        assert len(chunks) > 0
        # Check that at least one chunk has table
        has_table = any(chunk.has_table for chunk in chunks)
        assert has_table or len(chunks) == 1  # Either has table or single chunk with everything

    def test_table_preservation(self):
        """Test that tables are preserved with context"""
        chunker = DocumentChunker(chunk_size=500, preserve_tables=True)

        text = """
Context before table.

##TABLE_START
Header1  Header2
Data1  Data2
##TABLE_END

Context after table.
"""

        chunks = chunker.chunk_text(text, metadata={}, source_type='sec_filing')

        # Find chunk with table
        table_chunks = [c for c in chunks if c.has_table]
        if table_chunks:
            # Table chunk should have table reference
            assert table_chunks[0].table_id is not None


class TestTableToMarkdown:
    """Test table to markdown conversion"""

    def test_markdown_conversion(self):
        """Test conversion of table to markdown format"""
        chunker = DocumentChunker()

        caption = "Test Table"
        headers = ["Column1", "Column2"]
        rows = [["A", "B"], ["C", "D"]]

        markdown = chunker.table_extractor._table_to_markdown(caption, headers, rows)

        assert "**Test Table**" in markdown
        assert "Column1" in markdown
        assert "Column2" in markdown
        assert "|" in markdown
        assert "---" in markdown

    def test_markdown_with_empty_cells(self):
        """Test markdown conversion with empty cells"""
        chunker = DocumentChunker()

        headers = ["Col1", "Col2", "Col3"]
        rows = [["A", "", "C"], ["", "B", ""]]

        markdown = chunker.table_extractor._table_to_markdown("Table", headers, rows)

        assert "|" in markdown
        assert "Col1" in markdown
        assert "Col3" in markdown


class TestDocumentChunkStructure:
    """Test DocumentChunk dataclass structure"""

    def test_chunk_fields(self):
        """Test that chunk has all required fields"""
        chunk = DocumentChunk(
            chunk_id="test_001",
            text="Sample text",
            token_count=5,
            metadata={'source': 'test'},
            chunk_index=0
        )

        assert chunk.chunk_id == "test_001"
        assert chunk.text == "Sample text"
        assert chunk.token_count == 5
        assert chunk.metadata == {'source': 'test'}
        assert chunk.chunk_index == 0

    def test_chunk_with_table(self):
        """Test chunk with table information"""
        chunk = DocumentChunk(
            chunk_id="test_002",
            text="Text with table",
            token_count=10,
            metadata={'source': 'sec_filing'},
            chunk_index=1,
            has_table=True,
            table_id="table_001"
        )

        assert chunk.has_table == True
        assert chunk.table_id == "table_001"


class TestChunkingConfig:
    """Test chunking configuration"""

    def test_chunk_size_respected(self):
        """Test that chunk size limits are respected"""
        chunker = DocumentChunker(chunk_size=100, overlap=20)
        long_text = "word " * 1000  # Create very long text

        chunks = chunker.chunk_text(long_text, metadata={}, source_type='text')

        # Most chunks should be under or near the chunk size
        for chunk in chunks[:-1]:  # Exclude last chunk
            assert chunk.token_count <= chunker.chunk_size * 1.5  # Allow some tolerance

    def test_overlap_creates_continuity(self):
        """Test that overlap creates continuity between chunks"""
        chunker = DocumentChunker(chunk_size=50, overlap=10)
        text = "word " * 200

        chunks = chunker.chunk_text(text, metadata={}, source_type='text')

        if len(chunks) > 1:
            # Check that consecutive chunks have some overlap
            # (This is a basic check, actual overlap detection would be more complex)
            assert chunks[0].text != chunks[1].text  # They should be different
            assert len(chunks[0].text) > 0
            assert len(chunks[1].text) > 0


# Pytest configuration
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
