# src/data_processing/sec_parser.py
"""
SEC Filing Parser - Orchestrates complete SEC document processing

Handles:
- Document parsing (splitting tables and text)
- Table extraction and conversion
- LLM-based table summarization
- Text cleaning
- Section-aware chunking
"""

from typing import List, Dict, Any
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data_processing.document_parser import DocumentParser
from src.data_processing.table_extractor import TableExtractor
from src.data_processing.table_summarizer import TableSummarizer
from src.data_processing.text_cleaner import TextCleaner
from src.data_processing.chunking_engine import ChunkingEngine
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SECParser:
    """
    Orchestrator for SEC filing processing

    Complete workflow:
    1. Parse document (split tables and text)
    2. Extract and convert tables to markdown
    3. Summarize tables using LLM
    4. Clean text content
    5. Chunk with section-aware sizing
    """

    def __init__(self):
        """Initialize all processing components"""
        self.document_parser = DocumentParser()
        self.table_extractor = TableExtractor()
        self.table_summarizer = TableSummarizer()
        self.text_cleaner = TextCleaner()
        self.chunking_engine = ChunkingEngine()

        logger.info("SECParser initialized with all components")

    def parse_filing_section(
        self,
        section_content: str,
        section_code: str,
        section_name: str,
        filing_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse a complete SEC filing section

        Args:
            section_content: HTML content of the section
            section_code: Section code (e.g., '1A', '7')
            section_name: Section name (e.g., 'Risk Factors')
            filing_metadata: Metadata about the filing (ticker, filing_type, etc.)

        Returns:
            Dictionary containing:
            - text_chunks: List of text chunk dictionaries
            - table_chunks: List of table chunk dictionaries
            - statistics: Processing statistics
        """
        logger.info(
            f"Processing SEC section {section_code} ({section_name}) "
            f"for {filing_metadata.get('ticker', 'UNKNOWN')}"
        )

        # Step 1: Parse document into tables and text
        parsed_components = self.document_parser.parse_section(section_content)

        # Step 2: Process tables
        table_chunks = self._process_tables(
            tables=parsed_components.get('tables', []),
            section_code=section_code,
            section_name=section_name,
            filing_metadata=filing_metadata
        )

        # Step 3: Process text
        text_chunks = self._process_text(
            text_components=parsed_components.get('text_components', []),
            section_code=section_code,
            section_name=section_name,
            filing_metadata=filing_metadata
        )

        # Step 4: Compile statistics
        statistics = {
            'section_code': section_code,
            'section_name': section_name,
            'total_chunks': len(text_chunks) + len(table_chunks),
            'text_chunks': len(text_chunks),
            'table_chunks': len(table_chunks),
            'tables_found': len(parsed_components.get('tables', [])),
            'text_components': len(parsed_components.get('text_components', []))
        }

        logger.info(
            f"Section {section_code} processed: "
            f"{statistics['text_chunks']} text chunks, "
            f"{statistics['table_chunks']} table chunks"
        )

        return {
            'text_chunks': text_chunks,
            'table_chunks': table_chunks,
            'statistics': statistics
        }

    def _process_tables(
        self,
        tables: List[Dict[str, Any]],
        section_code: str,
        section_name: str,
        filing_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Process all tables in a section

        Args:
            tables: List of table dictionaries from document parser
            section_code: Section code
            section_name: Section name
            filing_metadata: Filing metadata

        Returns:
            List of table chunk dictionaries
        """
        table_chunks = []

        for i, table_data in enumerate(tables):
            try:
                # Extract table to markdown
                table_markdown = self.table_extractor.extract_table(
                    table_html=table_data.get('html', ''),
                    context_before=table_data.get('context_before', ''),
                    context_after=table_data.get('context_after', '')
                )

                # Summarize table using LLM
                summary = self.table_summarizer.summarize_table(
                    table_markdown=table_markdown,
                    section_name=section_name,
                    context=table_data.get('context_before', '')
                )

                # Create table chunk
                chunk = {
                    'text': f"{table_markdown}\n\n[Summary: {summary}]",
                    'chunk_type': 'table',
                    'contains_table': True,
                    'table_summary': summary,
                    'table_markdown': table_markdown,
                    'position': i,
                    'section_code': section_code,
                    'section_name': section_name,
                    **filing_metadata
                }

                table_chunks.append(chunk)

            except Exception as e:
                logger.error(
                    f"Error processing table {i} in section {section_code}: {e}"
                )
                continue

        return table_chunks

    def _process_text(
        self,
        text_components: List[str],
        section_code: str,
        section_name: str,
        filing_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Process text components in a section

        Args:
            text_components: List of text strings
            section_code: Section code
            section_name: Section name
            filing_metadata: Filing metadata

        Returns:
            List of text chunk dictionaries
        """
        # Combine all text components
        full_text = "\n\n".join(text_components)

        # Clean text
        cleaned_text = self.text_cleaner.clean(full_text)

        if not cleaned_text or len(cleaned_text) < 100:
            logger.warning(
                f"Section {section_code} has insufficient text after cleaning"
            )
            return []

        # Chunk with section-aware sizing
        chunks_with_metadata = self.chunking_engine.chunk_with_metadata(
            text=cleaned_text,
            source_type='sec',
            section_code=section_code,
            section_name=section_name,
            base_metadata=filing_metadata
        )

        # Add chunk type
        for chunk in chunks_with_metadata:
            chunk['chunk_type'] = 'text'
            chunk['contains_table'] = False
            chunk['section_code'] = section_code
            chunk['section_name'] = section_name

        return chunks_with_metadata

    def get_processing_summary(self, results: Dict[str, Any]) -> str:
        """
        Get human-readable processing summary

        Args:
            results: Results from parse_filing_section

        Returns:
            Summary string
        """
        stats = results.get('statistics', {})

        summary = f"""
        SEC Section Processing Summary
        ==============================
        Section: {stats.get('section_code')} - {stats.get('section_name')}

        Components Found:
        - Tables: {stats.get('tables_found', 0)}
        - Text Components: {stats.get('text_components', 0)}

        Chunks Created:
        - Total: {stats.get('total_chunks', 0)}
        - Text Chunks: {stats.get('text_chunks', 0)}
        - Table Chunks: {stats.get('table_chunks', 0)}
        """

        return summary.strip()
