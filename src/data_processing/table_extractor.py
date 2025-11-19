# src/data_processing/table_extractor.py
"""
Extract and process tables from SEC filings

Converts text-based tables to markdown format and extracts metadata
"""

import re
from typing import Dict, List, Optional, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class TableExtractor:
    """
    Extract and process tables from SEC filing text
    
    Features:
    - Parse text-based tables into structured format
    - Convert to markdown
    - Extract table metadata (dimensions, content type)
    """
    
    def __init__(self):
        logger.info("TableExtractor initialized")
    
    def parse_table(self, table_text: str) -> Dict[str, Any]:
        """
        Parse table text into structured format
        
        Args:
            table_text: Raw table text (without markers)
            
        Returns:
            Dictionary with parsed table data
            
        Example:
            Input: "Revenue | 2024\nProduct | $100M"
            Output: {
                'headers': ['Revenue', '2024'],
                'rows': [['Product', '$100M']],
                'row_count': 1,
                'col_count': 2
            }
        """
        if not table_text or not table_text.strip():
            logger.warning("Empty table text provided")
            return None
        
        lines = [line.strip() for line in table_text.split('\n') if line.strip()]
        
        if not lines:
            return None
        
        # Detect delimiter (| or multiple spaces)
        if '|' in lines[0]:
            # Pipe-delimited table
            cells = [[cell.strip() for cell in line.split('|') if cell.strip()] 
                     for line in lines]
        else:
            # Space-delimited table (need to handle variable spacing)
            # Use regex to split on 2+ spaces
            cells = [[cell.strip() for cell in re.split(r'\s{2,}', line) if cell.strip()]
                     for line in lines]
        
        # Remove empty rows
        cells = [row for row in cells if row]
        
        if not cells:
            return None
        
        # First row is typically headers
        headers = cells[0]
        rows = cells[1:] if len(cells) > 1 else []
        
        # Calculate dimensions
        max_cols = max(len(row) for row in cells) if cells else 0
        
        parsed = {
            'headers': headers,
            'rows': rows,
            'row_count': len(rows),
            'col_count': max_cols,
            'total_cells': len(headers) + sum(len(row) for row in rows)
        }
        
        logger.debug(
            f"Parsed table: {parsed['row_count']} rows × {parsed['col_count']} cols"
        )
        
        return parsed
    
    def convert_to_markdown(self, table_data: Dict) -> str:
        """
        Convert parsed table to markdown format
        
        Args:
            table_data: Parsed table dictionary
            
        Returns:
            Markdown-formatted table string
        """
        if not table_data or not table_data.get('headers'):
            return ""
        
        headers = table_data['headers']
        rows = table_data['rows']
        
        # Build markdown table
        markdown_lines = []
        
        # Header row
        markdown_lines.append('| ' + ' | '.join(headers) + ' |')
        
        # Separator row
        markdown_lines.append('|' + '|'.join(['---' for _ in headers]) + '|')
        
        # Data rows
        for row in rows:
            # Pad row if shorter than headers
            padded_row = row + [''] * (len(headers) - len(row))
            markdown_lines.append('| ' + ' | '.join(padded_row[:len(headers)]) + ' |')
        
        markdown_table = '\n'.join(markdown_lines)
        
        logger.debug(f"Converted to markdown: {len(markdown_lines)} lines")
        
        return markdown_table
    
    def extract_table_metadata(self, table_data: Dict, table_text: str) -> Dict:
        """
        Extract metadata about table content
        
        Args:
            table_data: Parsed table dictionary
            table_text: Original table text
            
        Returns:
            Metadata dictionary
        """
        metadata = {
            'row_count': table_data['row_count'],
            'col_count': table_data['col_count'],
            'has_numeric_data': self._detect_numeric_data(table_data),
            'has_multi_year_data': self._detect_multi_year_data(table_data),
            'has_currency_values': self._detect_currency(table_text),
            'table_type': self._classify_table_type(table_data)
        }
        
        # Extract years if multi-year table
        if metadata['has_multi_year_data']:
            metadata['year_columns'] = self._extract_years(table_data)
        
        return metadata
    
    def _detect_numeric_data(self, table_data: Dict) -> bool:
        """Check if table contains numeric data"""
        all_cells = table_data['headers'] + [cell for row in table_data['rows'] for cell in row]
        
        # Check for numbers, currency symbols, percentages
        numeric_pattern = r'[\d,.$%]'
        
        for cell in all_cells:
            if re.search(numeric_pattern, str(cell)):
                return True
        
        return False
    
    def _detect_multi_year_data(self, table_data: Dict) -> bool:
        """Check if table has multiple year columns"""
        headers = table_data['headers']
        
        # Look for year patterns (2020, 2021, etc.)
        year_pattern = r'20\d{2}'
        year_count = sum(1 for header in headers if re.search(year_pattern, str(header)))
        
        return year_count >= 2
    
    def _extract_years(self, table_data: Dict) -> List[int]:
        """Extract year values from headers"""
        headers = table_data['headers']
        year_pattern = r'20\d{2}'
        
        years = []
        for header in headers:
            match = re.search(year_pattern, str(header))
            if match:
                years.append(int(match.group()))
        
        return sorted(years, reverse=True)
    
    def _detect_currency(self, text: str) -> bool:
        """Check if table contains currency values"""
        currency_pattern = r'[$€£¥]\s*[\d,]+'
        return bool(re.search(currency_pattern, text))
    
    def _classify_table_type(self, table_data: Dict) -> str:
        """
        Classify table type based on content
        
        Returns:
            'financial', 'comparison', 'list', or 'other'
        """
        headers_text = ' '.join(table_data['headers']).lower()
        
        # Financial keywords
        financial_keywords = ['revenue', 'income', 'expense', 'assets', 'liabilities', 
                              'equity', 'cash', 'earnings', 'profit', 'loss']
        
        if any(kw in headers_text for kw in financial_keywords):
            return 'financial'
        
        # Comparison (multiple years/periods)
        if self._detect_multi_year_data(table_data):
            return 'comparison'
        
        # List (single column or simple enumeration)
        if table_data['col_count'] <= 2:
            return 'list'
        
        return 'other'
    
    def process_table(
        self,
        table_component: Dict,
        context_before: str = "",
        context_after: str = ""
    ) -> Dict[str, Any]:
        """
        Complete table processing pipeline
        
        Args:
            table_component: Table component from parser
            context_before: Context sentences before table
            context_after: Context sentences after table
            
        Returns:
            Processed table dictionary with all enhancements
        """
        table_text = table_component['content']
        
        # Parse table
        parsed = self.parse_table(table_text)
        
        if not parsed:
            logger.error("Failed to parse table")
            return None
        
        # Convert to markdown
        markdown = self.convert_to_markdown(parsed)
        
        # Extract metadata
        metadata = self.extract_table_metadata(parsed, table_text)
        
        # Build processed table
        processed = {
            'raw_table': table_text,
            'markdown_table': markdown,
            'structured_data': parsed,
            'metadata': metadata,
            'context_before': context_before,
            'context_after': context_after,
            'component_index': table_component['index_in_section'],
            'position': table_component['position']
        }
        
        logger.debug(
            f"Processed table: {metadata['table_type']}, "
            f"{parsed['row_count']}×{parsed['col_count']}"
        )
        
        return processed


# ==================== TESTING ====================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("TESTING TABLE EXTRACTOR")
    print("="*70 + "\n")
    
    extractor = TableExtractor()
    
    # Test 1: Parse pipe-delimited table
    print("Test 1: Parse pipe-delimited table")
    print("-" * 70)
    
    table_text_1 = """Revenue by Segment (in millions)
                        2024      2023      2022
Product Sales         $45,200   $42,100   $39,800
Services              $12,300   $11,500   $10,200
Total Revenue         $57,500   $53,600   $50,000"""
    
    parsed = extractor.parse_table(table_text_1)
    print(f"✅ Parsed: {parsed['row_count']} rows × {parsed['col_count']} cols")
    print(f"   Headers: {parsed['headers']}")
    print(f"   First row: {parsed['rows'][0] if parsed['rows'] else 'N/A'}")
    
    # Test 2: Convert to markdown
    print("\n\nTest 2: Convert to markdown")
    print("-" * 70)
    
    markdown = extractor.convert_to_markdown(parsed)
    print("✅ Markdown output:")
    print(markdown)
    
    # Test 3: Extract metadata
    print("\n\nTest 3: Extract table metadata")
    print("-" * 70)
    
    metadata = extractor.extract_table_metadata(parsed, table_text_1)
    print(f"✅ Metadata:")
    for key, value in metadata.items():
        print(f"   {key}: {value}")
    
    # Test 4: Complete processing
    print("\n\nTest 4: Complete table processing")
    print("-" * 70)
    
    table_component = {
        'type': 'table',
        'content': table_text_1,
        'position': 100,
        'index_in_section': 1
    }
    
    context_before = "Our revenue performance exceeded expectations. The company maintained strong growth."
    context_after = "This growth was driven by product innovation."
    
    processed = extractor.process_table(table_component, context_before, context_after)
    
    print(f"✅ Processed table:")
    print(f"   Type: {processed['metadata']['table_type']}")
    print(f"   Has multi-year: {processed['metadata']['has_multi_year_data']}")
    print(f"   Context before: {processed['context_before'][:60]}...")
    print(f"   Context after: {processed['context_after'][:60]}...")
    
    print("\n" + "="*70)
    print("✅ ALL TABLE EXTRACTOR TESTS PASSED")
    print("="*70 + "\n")