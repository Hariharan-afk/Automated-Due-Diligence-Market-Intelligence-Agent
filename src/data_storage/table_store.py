"""
Table Storage Utility
Handles storage and retrieval of SEC filing tables
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TableStore:
    """
    Simple JSON-based storage for SEC filing tables
    Can be extended to use database in production
    """
    
    def __init__(self, storage_path: str = "data/tables"):
        """
        Initialize table storage
        
        Args:
            storage_path: Directory to store table JSON files
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"TableStore initialized at: {self.storage_path}")
    
    def save_tables(self, tables: List[Dict], filename: Optional[str] = None) -> str:
        """
        Save tables to JSON file
        
        Args:
            tables: List of table metadata dictionaries
            filename: Optional custom filename
        
        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tables_{timestamp}.json"
        
        filepath = self.storage_path / filename
        
        # Create index for quick lookups
        tables_dict = {table['table_id']: table for table in tables}
        
        data = {
            'metadata': {
                'total_tables': len(tables),
                'saved_at': datetime.utcnow().isoformat(),
                'version': '1.0'
            },
            'tables': tables_dict
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(tables)} tables to {filepath}")
        return str(filepath)
    
    def load_tables(self, filename: str) -> Dict[str, Dict]:
        """
        Load tables from JSON file
        
        Args:
            filename: Name of file to load
        
        Returns:
            Dict mapping table_id -> table_metadata
        """
        filepath = self.storage_path / filename
        
        if not filepath.exists():
            logger.error(f"Table file not found: {filepath}")
            return {}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        tables_dict = data.get('tables', {})
        logger.info(f"Loaded {len(tables_dict)} tables from {filepath}")
        return tables_dict
    
    def get_table(self, table_id: str, tables_dict: Dict[str, Dict]) -> Optional[Dict]:
        """
        Get a specific table by ID
        
        Args:
            table_id: Table identifier
            tables_dict: Tables dictionary
        
        Returns:
            Table metadata or None
        """
        return tables_dict.get(table_id)
    
    def reconstruct_chunk_with_tables(
        self, 
        chunk_text: str,
        table_references: List[str],
        tables_dict: Dict[str, Dict],
        format: str = 'markdown'
    ) -> str:
        """
        Reconstruct chunk by replacing table references with actual tables
        
        Args:
            chunk_text: Text with table references
            table_references: List of table IDs in this chunk
            tables_dict: All available tables
            format: 'markdown' or 'html'
        
        Returns:
            Reconstructed text with tables
        """
        if not table_references:
            return chunk_text
        
        import re
        reconstructed = chunk_text
        
        for table_id in table_references:
            table = self.get_table(table_id, tables_dict)
            
            if table:
                # Find the placeholder pattern
                placeholder_pattern = rf"\[TABLE_REF: {re.escape(table_id)}\]\s*Summary: [^\n]*"
                
                # Get table in requested format
                if format == 'markdown':
                    table_content = table.get('table_markdown', '')
                elif format == 'html':
                    table_content = table.get('table_html', '')
                else:
                    table_content = table.get('table_markdown', '')
                
                # Replace placeholder with actual table
                reconstructed = re.sub(
                    placeholder_pattern,
                    f"\n\n{table_content}\n\n",
                    reconstructed,
                    count=1
                )
                logger.debug(f"Replaced {table_id} with actual table")
            else:
                logger.warning(f"Table {table_id} not found in tables_dict")
        
        return reconstructed
    
    def get_tables_for_filing(
        self, 
        filing_accession: str,
        tables_dict: Dict[str, Dict]
    ) -> List[Dict]:
        """
        Get all tables for a specific filing
        
        Args:
            filing_accession: Filing accession number
            tables_dict: All available tables
        
        Returns:
            List of tables for the filing
        """
        filing_tables = [
            table for table in tables_dict.values()
            if table.get('filing_accession') == filing_accession
        ]
        return filing_tables
    
    def get_summary_statistics(self, tables_dict: Dict[str, Dict]) -> Dict:
        """
        Get statistics about stored tables
        
        Args:
            tables_dict: Tables dictionary
        
        Returns:
            Statistics dictionary
        """
        if not tables_dict:
            return {'total': 0}
        
        # Count by filing type
        filing_types = {}
        sections = {}
        companies = {}
        
        for table in tables_dict.values():
            # By filing type
            ftype = table.get('filing_type', 'Unknown')
            filing_types[ftype] = filing_types.get(ftype, 0) + 1
            
            # By section
            section = table.get('section', 'Unknown')
            sections[section] = sections.get(section, 0) + 1
            
            # By company
            company = table.get('company', 'Unknown')
            companies[company] = companies.get(company, 0) + 1
        
        return {
            'total_tables': len(tables_dict),
            'by_filing_type': filing_types,
            'by_section': sections,
            'by_company': companies
        }


# Example usage for RAG retrieval
def example_rag_retrieval(query: str, vector_store, table_store: TableStore, tables_filename: str):
    """
    Example of how to use table reconstruction in RAG pipeline
    
    Args:
        query: User query
        vector_store: Vector database with chunks
        table_store: TableStore instance
        tables_filename: Filename of stored tables
    """
    # Load tables
    tables_dict = table_store.load_tables(tables_filename)
    
    # Retrieve relevant chunks (with table references/summaries)
    relevant_chunks = vector_store.similarity_search(query, k=5)
    
    # Reconstruct chunks with actual tables if needed
    full_contexts = []
    for chunk in relevant_chunks:
        if chunk.get('has_tables'):
            # Replace table references with actual tables
            reconstructed = table_store.reconstruct_chunk_with_tables(
                chunk_text=chunk['chunk_text'],
                table_references=chunk['table_references'],
                tables_dict=tables_dict,
                format='markdown'
            )
            full_contexts.append(reconstructed)
        else:
            full_contexts.append(chunk['chunk_text'])
    
    # Send to LLM
    context = "\n\n---\n\n".join(full_contexts)
    # response = llm.generate(f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:")
    
    return context


if __name__ == "__main__":
    # Test table storage
    logging.basicConfig(level=logging.INFO)
    
    # Create test tables
    test_tables = [
        {
            'table_id': 'TABLE_AAPL_Item_7_0',
            'company': 'Apple Inc.',
            'section': '7',
            'summary': 'Revenue by product category',
            'table_markdown': '| Product | Revenue |\n|---------|-------|\n| iPhone | 45B |'
        }
    ]
    
    # Test storage
    store = TableStore(storage_path="test_tables")
    saved_path = store.save_tables(test_tables, "test.json")
    print(f"Saved to: {saved_path}")
    
    # Load and get stats
    loaded = store.load_tables("test.json")
    stats = store.get_summary_statistics(loaded)
    print(f"Statistics: {stats}")
