# src/data_processing/table_detector.py
"""Financial table detection using heuristics and regex patterns"""

import re
from typing import Dict, List, Any, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class FinancialTableDetector:
    """
    Detects and classifies financial tables in markdown text
    
    Uses heuristic scoring based on:
    - Currency symbols and monetary values
    - Financial terminology
    - Table structure consistency
    - Document context
    """
    
    def __init__(self, confidence_threshold: float = 0.6):
        """
        Initialize table detector
        
        Args:
            confidence_threshold: Minimum confidence to classify as financial table
        """
        self.confidence_threshold = confidence_threshold
        
        logger.info(f"FinancialTableDetector initialized (threshold: {confidence_threshold})")
    
    def analyze_chunk(self, chunk: str) -> Dict[str, Any]:
        """
        Analyze a chunk and determine if it contains financial tables
        
        Args:
            chunk: Text chunk (markdown)
        
        Returns:
            Dict with:
                - is_financial_table: bool
                - confidence: float (0.0 to 1.0)
                - table_type: str or None
                - tables_found: int
                - features: dict
        """
        result = {
            'is_financial_table': False,
            'confidence': 0.0,
            'table_type': None,
            'features': {},
            'tables_found': 0
        }
        
        # Extract valid tables from the chunk
        tables = self.extract_tables_from_chunk(chunk)
        result['tables_found'] = len(tables)
        
        # If no valid tables found, definitely not a financial table
        if len(tables) == 0:
            result['confidence'] = 0.0
            return result
        
        # Analyze each table and take the highest confidence financial table
        best_confidence = 0.0
        best_table_type = None
        
        for table in tables:
            table_analysis = self.analyze_single_table(table, chunk)
            if table_analysis['is_financial'] and table_analysis['confidence'] > best_confidence:
                best_confidence = table_analysis['confidence']
                best_table_type = table_analysis['table_type']
                result['is_financial_table'] = True
        
        result['confidence'] = best_confidence
        result['table_type'] = best_table_type
        result['features'] = self.extract_features(chunk, tables)
        
        return result
    
    def analyze_single_table(self, table_markdown: str, chunk_context: str) -> Dict[str, Any]:
        """
        Analyze a single table to determine if it's financial
        
        Args:
            table_markdown: Markdown table text
            chunk_context: Full chunk context
        
        Returns:
            Dict with is_financial, confidence, table_type
        """
        analysis = {
            'is_financial': False,
            'confidence': 0.0,
            'table_type': None
        }
        
        score = 0
        max_score = 11
        
        # Check for currency symbols in table
        currency_pattern = r'[\$€£¥]\s*[\d,]+'
        if re.search(currency_pattern, table_markdown):
            score += 3
        
        # Check for monetary values (numbers with commas)
        monetary_pattern = r'\b\d{1,3}(?:,\d{3})+\b'
        monetary_matches = re.findall(monetary_pattern, table_markdown)
        if len(monetary_matches) > 2:
            score += 2
        
        # Check for financial periods in table
        period_pattern = r'(20\d{2}|Q[1-4]|FY\s*\d{4})'
        period_matches = re.findall(period_pattern, table_markdown)
        if len(period_matches) > 1:
            score += 2
        
        # Check for financial terms in table
        financial_terms = [
            'revenue', 'income', 'expense', 'cash', 'flow', 'assets', 'liabilities',
            'equity', 'profit', 'loss', 'earnings', 'depreciation', 'amortization',
            'sales', 'operating', 'investing', 'financing', 'stockholders'
        ]
        table_lower = table_markdown.lower()
        financial_term_count = sum(1 for term in financial_terms if term in table_lower)
        if financial_term_count > 1:
            score += min(2, financial_term_count)
        
        # Check context around the table
        chunk_lower = chunk_context.lower()
        financial_headers = [
            'consolidated statements of cash flows',
            'consolidated statements of operations',
            'consolidated balance sheets',
            'consolidated statements of comprehensive income',
            'statements of stockholders',
            '(in millions)',
            '(in millions, except per share data)'
        ]
        if any(header in chunk_lower for header in financial_headers):
            score += 2
        
        # Negative indicators
        if 'page' in table_lower and len(monetary_matches) < 3:
            score -= 2
        
        # Calculate confidence
        confidence = min(1.0, max(0.0, score / max_score))
        analysis['confidence'] = confidence
        
        if score >= 3:
            analysis['is_financial'] = True
            analysis['table_type'] = self.classify_table_type(table_markdown, chunk_context)
        
        return analysis
    
    def classify_table_type(self, table_markdown: str, chunk_context: str) -> Optional[str]:
        """
        Classify the type of financial table
        
        Returns: 'cash_flow', 'income', 'balance_sheet', 'comprehensive_income', 
                 'equity', or 'other'
        """
        combined_text = (chunk_context + ' ' + table_markdown).lower()
        
        if 'cash flow' in combined_text:
            return 'cash_flow'
        elif 'statement of operations' in combined_text or 'income statement' in combined_text:
            return 'income'
        elif 'balance sheet' in combined_text:
            return 'balance_sheet'
        elif 'comprehensive income' in combined_text:
            return 'comprehensive_income'
        elif 'stockholders' in combined_text or 'equity' in combined_text:
            return 'equity'
        else:
            return 'other'
    
    def extract_tables_from_chunk(self, chunk: str) -> List[str]:
        """
        Extract all valid tables from a chunk
        
        Args:
            chunk: Text chunk
        
        Returns:
            List of table markdown strings
        """
        lines = chunk.strip().split('\n')
        tables = []
        current_table = []
        in_table = False
        
        for line in lines:
            if self.looks_like_table_row(line):
                if not in_table:
                    in_table = True
                current_table.append(line)
            else:
                if in_table and current_table:
                    # We've reached the end of a table
                    if self.validate_table_structure(current_table):
                        tables.append('\n'.join(current_table))
                    current_table = []
                    in_table = False
        
        # Don't forget the last table
        if in_table and current_table and self.validate_table_structure(current_table):
            tables.append('\n'.join(current_table))
        
        return tables
    
    @staticmethod
    def looks_like_table_row(line: str) -> bool:
        """
        Check if a line looks like a table row
        
        Args:
            line: Text line
        
        Returns:
            True if line appears to be a table row
        """
        if not line.startswith('|') and not line.endswith('|'):
            return False
        
        # Count pipe characters - real tables usually have multiple
        pipe_count = line.count('|')
        if pipe_count < 2:
            return False
        
        # Check if it has proper table cell structure
        cells = [cell.strip() for cell in line.split('|') if cell.strip()]
        if len(cells) < 2:
            return False
        
        return True
    
    def validate_table_structure(self, table_lines: List[str]) -> bool:
        """
        Validate that we have a proper markdown table structure
        
        Args:
            table_lines: List of table lines
        
        Returns:
            True if valid table structure
        """
        if len(table_lines) < 2:
            return False
        
        # Check for header separator line (--- between pipes)
        has_separator = any(self.is_separator_line(line) for line in table_lines)
        
        # Check consistency of column count
        col_counts = []
        for line in table_lines:
            if not self.is_separator_line(line):
                col_count = line.count('|')
                col_counts.append(col_count)
        
        if col_counts:
            # Check if column counts are consistent (allow for small variations)
            min_cols = min(col_counts)
            max_cols = max(col_counts)
            if max_cols - min_cols > 2:  # Allow some inconsistency in financial tables
                return False
        
        # Additional validation: check if it has substantial content
        substantial_content = any(
            len(line.strip()) > 20 and not self.is_separator_line(line)
            for line in table_lines
        )
        
        return substantial_content and len(table_lines) >= 2
    
    @staticmethod
    def is_separator_line(line: str) -> bool:
        """Check if line is a markdown table separator (---)"""
        line = line.strip()
        if not line.startswith('|'):
            return False
        
        # Check for separator pattern: | --- | --- | etc.
        parts = line.split('|')
        separator_count = 0
        total_parts = 0
        
        for part in parts:
            part = part.strip()
            if part:
                total_parts += 1
                if re.match(r'^[\-\s:]+$', part):
                    separator_count += 1
        
        return separator_count > 0 and separator_count / total_parts > 0.5
    
    def extract_features(self, chunk: str, tables: List[str]) -> Dict[str, Any]:
        """Extract additional features from chunk"""
        features = {
            'total_tables': len(tables),
            'has_currency_symbols': bool(re.search(r'[\$€£¥]', chunk)),
            'has_monetary_values': bool(re.search(r'\b\d{1,3}(?:,\d{3})+\b', chunk)),
            'has_financial_terms': any(
                term in chunk.lower() 
                for term in ['revenue', 'income', 'cash', 'assets', 'liabilities']
            )
        }
        
        return features
    
    def is_high_confidence_financial_table(self, chunk: str) -> bool:
        """
        Check if chunk contains high-confidence financial table
        
        Args:
            chunk: Text chunk
        
        Returns:
            True if confidence >= threshold
        """
        analysis = self.analyze_chunk(chunk)
        return analysis['is_financial_table'] and analysis['confidence'] >= self.confidence_threshold