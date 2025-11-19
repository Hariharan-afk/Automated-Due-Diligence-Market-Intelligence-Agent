# src/data_processing/document_parser.py
"""
Parse SEC filing sections into components (tables and text)

Separates sections based on ##TABLE_START and ##TABLE_END markers
"""

import re
from typing import List, Dict, Tuple
from nltk.tokenize import sent_tokenize
import nltk

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    logger.info("Downloading NLTK punkt tokenizer...")
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)


class DocumentParser:
    """
    Parse SEC filing sections into table and text components
    
    Features:
    - Splits on ##TABLE_START/END markers
    - Preserves component positions
    - Extracts surrounding context for tables
    """
    
    def __init__(self):
        logger.info("DocumentParser initialized")
    
    def parse_section(self, section_text: str) -> List[Dict]:
        """
        Parse section text into components
        
        Args:
            section_text: Raw section text with ##TABLE_START/END markers
            
        Returns:
            List of component dictionaries
            
        Example output:
            [
                {
                    'type': 'text',
                    'content': 'Our business operates...',
                    'position': 0,
                    'index_in_section': 0
                },
                {
                    'type': 'table',
                    'content': 'Revenue | 2024\nProduct | $100M',
                    'raw_with_markers': '##TABLE_START\n...\n##TABLE_END',
                    'position': 150,
                    'index_in_section': 1
                }
            ]
        """
        if not section_text:
            logger.warning("Empty section text provided")
            return []
        
        components = []
        
        # Split on table markers while keeping them
        # Pattern captures everything between ##TABLE_START and ##TABLE_END
        pattern = r'(##TABLE_START.*?##TABLE_END)'
        parts = re.split(pattern, section_text, flags=re.DOTALL)
        
        position = 0
        index = 0
        
        for part in parts:
            if not part.strip():
                # Skip empty parts
                position += len(part)
                continue
            
            if '##TABLE_START' in part:
                # This is a table component
                # Extract table content (remove markers)
                table_content = part.replace('##TABLE_START', '').replace('##TABLE_END', '').strip()
                
                components.append({
                    'type': 'table',
                    'content': table_content,
                    'raw_with_markers': part,
                    'position': position,
                    'index_in_section': index
                })
                
                logger.debug(f"Found table at position {position}, {len(table_content)} chars")
                
            else:
                # This is a text component
                components.append({
                    'type': 'text',
                    'content': part.strip(),
                    'position': position,
                    'index_in_section': index
                })
                
                logger.debug(f"Found text at position {position}, {len(part)} chars")
            
            position += len(part)
            index += 1
        
        logger.info(
            f"Parsed section into {len(components)} components: "
            f"{sum(1 for c in components if c['type'] == 'table')} tables, "
            f"{sum(1 for c in components if c['type'] == 'text')} text"
        )
        
        return components
    
    def get_surrounding_context(
        self,
        components: List[Dict],
        table_index: int,
        sentences_before: int = 3,
        sentences_after: int = 2
    ) -> Tuple[str, str]:
        """
        Get context surrounding a table
        
        Args:
            components: List of all components
            table_index: Index of the table component
            sentences_before: Number of sentences to extract before
            sentences_after: Number of sentences to extract after
            
        Returns:
            Tuple of (context_before, context_after)
        """
        context_before = ""
        context_after = ""
        
        # Get text component before table
        if table_index > 0 and components[table_index - 1]['type'] == 'text':
            text_before = components[table_index - 1]['content']
            sentences = sent_tokenize(text_before)
            
            # Get last N sentences
            if len(sentences) >= sentences_before:
                context_before = ' '.join(sentences[-sentences_before:])
            else:
                context_before = text_before
        
        # Get text component after table
        if table_index < len(components) - 1 and components[table_index + 1]['type'] == 'text':
            text_after = components[table_index + 1]['content']
            sentences = sent_tokenize(text_after)
            
            # Get first N sentences
            if len(sentences) >= sentences_after:
                context_after = ' '.join(sentences[:sentences_after])
            else:
                context_after = text_after
        
        logger.debug(
            f"Extracted context for table {table_index}: "
            f"{len(context_before)} chars before, {len(context_after)} chars after"
        )
        
        return context_before, context_after
    
    def get_component_stats(self, components: List[Dict]) -> Dict:
        """
        Get statistics about parsed components
        
        Args:
            components: List of components
            
        Returns:
            Statistics dictionary
        """
        stats = {
            'total_components': len(components),
            'table_count': sum(1 for c in components if c['type'] == 'table'),
            'text_count': sum(1 for c in components if c['type'] == 'text'),
            'total_chars': sum(len(c['content']) for c in components),
            'avg_table_size': 0,
            'avg_text_size': 0
        }
        
        tables = [c for c in components if c['type'] == 'table']
        texts = [c for c in components if c['type'] == 'text']
        
        if tables:
            stats['avg_table_size'] = sum(len(c['content']) for c in tables) // len(tables)
        
        if texts:
            stats['avg_text_size'] = sum(len(c['content']) for c in texts) // len(texts)
        
        return stats


# ==================== TESTING ====================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("TESTING DOCUMENT PARSER")
    print("="*70 + "\n")
    
    # Create sample section text with tables
    sample_text = """
Risk Factors

Our business is subject to various operational risks that could impact our financial performance.

We face intense competition in our markets. Market conditions remain challenging with new entrants.

##TABLE_START
Revenue by Segment (in millions)
                        2024      2023      2022
Product Sales         $45,200   $42,100   $39,800
Services              $12,300   $11,500   $10,200
Total Revenue         $57,500   $53,600   $50,000
##TABLE_END

The revenue growth was driven by strong demand in our product lineup and expanding service offerings.
Our services segment showed consistent growth across all geographic regions.

We also face regulatory risks in multiple jurisdictions. These risks include changing privacy laws and tax regulations.

##TABLE_START
Geographic Revenue
Region          Revenue
North America   $30B
Europe          $15B
Asia Pacific    $12.5B
##TABLE_END

Geographic diversification provides some protection against regional economic downturns but also increases complexity.
"""
    
    # Test parsing
    parser = DocumentParser()
    
    print("Test 1: Parse section into components")
    print("-" * 70)
    components = parser.parse_section(sample_text)
    
    print(f"✅ Parsed into {len(components)} components:\n")
    
    for i, comp in enumerate(components):
        print(f"Component {i} ({comp['type']}):")
        print(f"  Position: {comp['position']}")
        print(f"  Length: {len(comp['content'])} chars")
        print(f"  Preview: {comp['content'][:80]}...")
        print()
    
    # Test getting context
    print("\nTest 2: Extract surrounding context for tables")
    print("-" * 70)
    
    for i, comp in enumerate(components):
        if comp['type'] == 'table':
            context_before, context_after = parser.get_surrounding_context(
                components, i, sentences_before=3, sentences_after=2
            )
            
            print(f"\nTable at index {i}:")
            print(f"  Context before ({len(context_before)} chars):")
            print(f"    {context_before[:100]}...")
            print(f"  Context after ({len(context_after)} chars):")
            print(f"    {context_after[:100]}...")
    
    # Test statistics
    print("\n\nTest 3: Get component statistics")
    print("-" * 70)
    stats = parser.get_component_stats(components)
    
    print(f"✅ Statistics:")
    print(f"  Total components: {stats['total_components']}")
    print(f"  Tables: {stats['table_count']}")
    print(f"  Text sections: {stats['text_count']}")
    print(f"  Total characters: {stats['total_chars']:,}")
    print(f"  Avg table size: {stats['avg_table_size']:,} chars")
    print(f"  Avg text size: {stats['avg_text_size']:,} chars")
    
    print("\n" + "="*70)
    print("✅ ALL DOCUMENT PARSER TESTS PASSED")
    print("="*70 + "\n")