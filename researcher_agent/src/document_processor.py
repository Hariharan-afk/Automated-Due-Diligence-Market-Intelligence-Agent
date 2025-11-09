# researcher_agent/src/document_processor.py
import re
from typing import List, Dict, Tuple
from nltk.tokenize import sent_tokenize
import nltk

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

from utils.config import config


class DocumentProcessor:
    """Handles parsing and chunking of SEC filing sections"""
    
    def __init__(self):
        self.text_chunk_size = config.TEXT_CHUNK_SIZE
        self.text_chunk_overlap = config.TEXT_CHUNK_OVERLAP
    
    def parse_section_components(self, section_text: str) -> List[Dict]:
        """
        Parse section text and identify tables vs narrative text
        
        Args:
            section_text: Raw section text with ##TABLE_START/END markers
            
        Returns:
            List of components with type, content, and position
        """
        components = []
        
        # Split on table markers while keeping them
        pattern = r'(##TABLE_START.*?##TABLE_END)'
        parts = re.split(pattern, section_text, flags=re.DOTALL)
        
        position = 0
        for i, part in enumerate(parts):
            if not part.strip():
                continue
            
            if '##TABLE_START' in part:
                # Extract table content (remove markers)
                table_content = part.replace('##TABLE_START', '').replace('##TABLE_END', '').strip()
                
                components.append({
                    'type': 'table',
                    'content': table_content,
                    'raw': part,
                    'position': position,
                    'index_in_section': i
                })
            else:
                components.append({
                    'type': 'text',
                    'content': part.strip(),
                    'position': position,
                    'index_in_section': i
                })
            
            position += len(part)
        
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
            sentences_before: Number of sentences to extract before table
            sentences_after: Number of sentences to extract after table
            
        Returns:
            Tuple of (context_before, context_after)
        """
        context_before = ""
        context_after = ""
        
        # Look back for text context
        if table_index > 0 and components[table_index - 1]['type'] == 'text':
            text_before = components[table_index - 1]['content']
            sentences = sent_tokenize(text_before)
            context_before = ' '.join(sentences[-sentences_before:]) if len(sentences) >= sentences_before else text_before
        
        # Look forward for text context
        if table_index < len(components) - 1 and components[table_index + 1]['type'] == 'text':
            text_after = components[table_index + 1]['content']
            sentences = sent_tokenize(text_after)
            context_after = ' '.join(sentences[:sentences_after]) if len(sentences) >= sentences_after else text_after
        
        return context_before, context_after
    
    def semantic_chunk_text(self, text: str) -> List[str]:
        """
        Apply semantic chunking to narrative text
        
        Args:
            text: Text content to chunk
            
        Returns:
            List of text chunks
        """
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.text_chunk_size,
            chunk_overlap=self.text_chunk_overlap,
            length_function=lambda t: len(t.split()),  # Token-based counting
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        chunks = splitter.split_text(text)
        return chunks
    
    def count_tokens(self, text: str) -> int:
        """Approximate token count (word-based)"""
        return len(text.split())


# # Example usage
# if __name__ == "__main__":
#     processor = DocumentProcessor()
    
#     # Test parsing
#     sample_text = """
#     Risk Factors
    
#     Our business is subject to various operational risks.
    
#     ##TABLE_START
#     Revenue by Segment
#                         2024      2023
#     Product Sales     $45.2B    $42.1B
#     Services          $12.3B    $11.5B
#     ##TABLE_END
    
#     The increase in product sales was primarily driven by new product launches.
    
#     We also face regulatory risks in multiple jurisdictions.
#     """
    
#     components = processor.parse_section_components(sample_text)
    
#     print(f"Found {len(components)} components:")
#     for i, comp in enumerate(components):
#         print(f"{i}: {comp['type']} - {len(comp['content'])} chars")
        
#         if comp['type'] == 'table':
#             context_before, context_after = processor.get_surrounding_context(components, i)
#             print(f"   Context before: {context_before[:100]}...")
#             print(f"   Context after: {context_after[:100]}...")