"""
Table Processor for SEC Filings
Detects tables in section HTML, generates summaries, and replaces with references
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TableProcessor:
    """
    Processes tables in SEC filing sections:
    1. Detects tables using edgartools
    2. Generates unique IDs
    3. Creates summaries via LLM
    4. Replaces tables with references
    """
    
    def __init__(self, summarizer, min_table_size: int = 4):
        """
        Initialize table processor
        
        Args:
            summarizer: GroqTableSummarizer instance
            min_table_size: Minimum cells to process (skip tiny tables)
        """
        self.summarizer = summarizer
        self.min_table_size = min_table_size
        logger.info(f"Initialized TableProcessor (min_table_size={min_table_size})")
    
    def process_section(
        self, 
        section_html,  # Either HtmlDocument object or HTML string
        section_text: str,
        metadata: Dict
    ) -> Tuple[str, List[Dict]]:
        """
        Process a section: detect tables, summarize, and replace
        
        Args:
            section_html: HtmlDocument object OR HTML string
            section_text: Plain text of the section
            metadata: Section metadata (ticker, section, filing info, etc.)
        
        Returns:
            Tuple of (processed_text, tables_metadata)
            - processed_text: Text with tables replaced by references
            - tables_metadata: List of table metadata dicts
        """
        from edgar.files.html_documents import HtmlDocument
        
        # Handle both HtmlDocument objects and HTML strings
        if isinstance(section_html, HtmlDocument):
            html_doc = section_html  # Already an HtmlDocument
            logger.debug("Using provided HtmlDocument object")
        elif isinstance(section_html, str):
            # Parse HTML string to HtmlDocument
            html_doc = HtmlDocument.from_html(section_html)
            logger.debug("Parsed HTML string to HtmlDocument")  
        else:
            logger.warning(f"Invalid section_html type: {type(section_html)}, returning original text")
            return section_text, []
        
        if not html_doc:
            logger.warning("Could not get HtmlDocument, returning original text")
            return section_text, []
        
        # Get table blocks from the HtmlDocument
        table_blocks = html_doc.get_table_blocks()
        
        if not table_blocks:
            logger.debug(f"No tables found in {metadata.get('section', 'unknown')} section")
            return section_text, []
        
        logger.info(f"Found {len(table_blocks)} tables in {metadata.get('section', 'unknown')} section")
        
        # BUILD PROCESSED TEXT FROM BLOCKS (not text matching!)
        # This ensures 100% accurate positioning
        from edgar.files.html_documents import TableBlock, TextBlock
        
        processed_text = ""
        tables_metadata = []
        table_index = 0
        
        # Iterate through ALL blocks in order
        for block_idx, block in enumerate(html_doc.blocks):
            
            if isinstance(block, TableBlock):
                try:
                    # Get table content
                    table_df = block.to_dataframe()
                    num_cells = len(table_df) * len(table_df.columns)
                    
                    # Skip tiny tables only if threshold > 0
                    if self.min_table_size > 0 and num_cells < self.min_table_size:
                        logger.debug(f"Skipping small table {table_index} ({num_cells} cells)")
                        # Add table as-is (not processing it)
                        processed_text += block.get_text()
                        table_index += 1
                        continue
                    
                    logger.debug(f"Processing table {table_index} ({num_cells} cells)")
                    
                    # Generate unique table ID
                    table_id = self.generate_table_id(metadata, table_index)
                    
                    # Get table formats
                    table_markdown = block.to_markdown()
                    table_html = str(block.table_element)
                    
                    # Handle duplicate column names in DataFrame
                    df_for_json = table_df.copy()
                    if df_for_json.columns.duplicated().any():
                        # Deduplicate column names
                        cols = df_for_json.columns.tolist()
                        new_cols = []
                        seen = {}
                        for col in cols:
                            if col in seen:
                                seen[col] += 1
                                new_cols.append(f"{col}_{seen[col]}")
                            else:
                                seen[col] = 0
                                new_cols.append(col)
                        df_for_json.columns = new_cols
                        logger.debug(f"Table {table_index} had duplicate columns, renamed for JSON")
                    
                    # Convert to JSON with error handling
                    try:
                        dataframe_json = df_for_json.to_json(orient='records')
                    except Exception as json_err:
                        logger.warning(f"Could not convert table {table_index} to JSON: {json_err}")
                        dataframe_json = None
                    
                    # Generate summary with comprehensive metadata context
                    context = {
                        'ticker': metadata.get('ticker', ''),
                        'company': metadata.get('company', ''),
                        'filing_type': metadata.get('filing_type', ''),
                        'filing_year': metadata.get('filing_year', ''),
                        'fiscal_quarter': metadata.get('fiscal_quarter'),
                        'section': metadata.get('section', ''),
                        'section_name': metadata.get('section_name', '')
                    }
                    
                    summary = self.summarizer.summarize_table(table_markdown, context)
                    
                    # Create table metadata
                    table_meta = {
                        'table_id': table_id,
                        'filing_accession': metadata.get('accession_number', ''),
                        'ticker': metadata.get('ticker', ''),
                        'company': metadata.get('company', ''),
                        'filing_type': metadata.get('filing_type', ''),
                        'filing_date': metadata.get('filing_date', ''),
                        'section': metadata.get('section', ''),
                        'section_name': metadata.get('section_name', ''),
                        'table_index': table_index,
                        'block_index': block_idx,  # Track position in document
                        'summary': summary,
                        'table_markdown': table_markdown,
                        'table_html': table_html,
                        'dataframe_json': dataframe_json,
                        'num_rows': len(table_df),
                        'num_cols': len(table_df.columns),
                        'num_cells': num_cells,
                        'extracted_at': datetime.utcnow().isoformat()
                    }
                    
                    tables_metadata.append(table_meta)
                    
                    # INSERT TABLE PLACEHOLDER AT EXACT POSITION
                    table_placeholder = self._create_table_placeholder(table_id, summary)
                    processed_text += table_placeholder
                    
                    logger.debug(f"Inserted table {table_index} placeholder at position {len(processed_text)}")
                    table_index += 1
                    
                except Exception as e:
                    logger.error(f"Error processing table {table_index}: {e}")
                    # Fallback: add table text as-is
                    processed_text += block.get_text()
                    table_index += 1
            
            elif isinstance(block, TextBlock):
                # Add text blocks as-is
                processed_text += block.get_text()
            
            else:
                # Other block types (shouldn't happen often)
                processed_text += block.get_text()
        
        logger.info(f"Processed {len(tables_metadata)} tables in {metadata.get('section', 'unknown')} section")
        return processed_text, tables_metadata
    
    def generate_table_id(self, metadata: Dict, table_index: int) -> str:
        """
        Generate unique table ID
        
        Format: TABLE_{TICKER}_{SECTION}_{INDEX}
        Example: TABLE_AAPL_Item_7_0
        """
        ticker = metadata.get('ticker', 'UNKNOWN')
        section = metadata.get('section', 'UNK').replace(' ', '_').replace('.', '_')
        accession = metadata.get('accession_number', '').replace('-', '')[:10]
        
        # Create unique ID
        table_id = f"TABLE_{ticker}_{accession}_{section}_{table_index}"
        return table_id
    
    def _create_table_placeholder(self, table_id: str, summary: str) -> str:
        """Create formatted table placeholder with ID and summary"""
        placeholder = f"""
[TABLE_REF: {table_id}]
Summary: {summary}
"""
        return placeholder.strip()
    
    def extract_table_references(self, text: str) -> List[str]:
        """
        Extract all table reference IDs from text
        
        Args:
            text: Text containing table references
        
        Returns:
            List of table IDs
        """
        pattern = r'\[TABLE_REF: (TABLE_[^\]]+)\]'
        matches = re.findall(pattern, text)
        return matches
    
    def reconstruct_with_tables(
        self, 
        text: str, 
        tables_dict: Dict[str, Dict]
    ) -> str:
        """
        Reconstruct text by replacing table references with actual tables
        
        Args:
            text: Text with table references
            tables_dict: Dict mapping table_id -> table_metadata
        
        Returns:
            Text with tables restored
        """
        table_refs = self.extract_table_references(text)
        
        if not table_refs:
            return text
        
        reconstructed = text
        for table_id in table_refs:
            if table_id in tables_dict:
                table_data = tables_dict[table_id]
                
                # Get the placeholder
                placeholder_pattern = rf"\[TABLE_REF: {re.escape(table_id)}\]\s*Summary: [^\n]*"
                
                # Replace with actual table
                table_markdown = table_data.get('table_markdown', '')
                reconstructed = re.sub(
                    placeholder_pattern,
                    f"\n\n{table_markdown}\n\n",
                    reconstructed,
                    count=1
                )
        
        return reconstructed


if __name__ == "__main__":
    # Test the table processor
    logging.basicConfig(level=logging.INFO)
    
    from src.utils.table_summarizer import GroqTableSummarizer
    
    try:
        # Initialize
        summarizer = GroqTableSummarizer()
        processor = TableProcessor(summarizer, min_table_size=4)
        
        # Test HTML with a table
        test_html = """
        <html><body>
        <p>Revenue performance by product category:</p>
        <table>
            <tr><th>Product</th><th>Q1</th><th>Q2</th></tr>
            <tr><td>iPhone</td><td>45.2B</td><td>49.3B</td></tr>
            <tr><td>Mac</td><td>7.5B</td><td>8.2B</td></tr>
        </table>
        <p>Strong growth across all categories.</p>
        </body></html>
        """
        
        test_text = "Revenue performance by product category:\nProduct Q1 Q2\niPhone 45.2B 49.3B\nMac 7.5B 8.2B\nStrong growth."
        
        metadata = {
            'ticker': 'AAPL',
            'section': '7',
            'section_name': 'MD&A',
            'company': 'Apple Inc.',
            'filing_type': '10-K',
            'accession_number': '0000320193-25-000073'
        }
        
        # Process
        processed_text, tables = processor.process_section(test_html, test_text, metadata)
        
        print(f"\nProcessed Text:\n{processed_text}\n")
        print(f"Tables Metadata: {len(tables)} tables")
        for table in tables:
            print(f"  - {table['table_id']}: {table['summary'][:50]}...")
        
    except Exception as e:
        print(f"Error: {e}")
