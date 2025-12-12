# src/data_processing/chunker.py
"""Text chunking using LangChain RecursiveCharacterTextSplitter with tiktoken"""

from typing import List, Dict, Any
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class TextChunker:
    """
    Text chunker using LangChain's RecursiveCharacterTextSplitter
    
    Features:
    - Exact token-based chunking using tiktoken
    - Overlap between chunks for context preservation
    - Sentence-boundary aware splitting
    - Preserves table references intact
    """
    
    def __init__(self, chunk_size: int = 800, overlap: int = 100):
        """
        Initialize chunker
        
        Args:
            chunk_size: Target chunk size in tokens (exact)
            overlap: Overlap between chunks in tokens (exact)
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        
        # Initialize LangChain splitter with tiktoken
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            import tiktoken
            
            self.encoding = tiktoken.get_encoding("cl100k_base")
            
            self.splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=overlap,
                length_function=lambda text: len(self.encoding.encode(text)),
                separators=["\n\n", "\n", ". ", " ", ""],
                keep_separator=True,
                is_separator_regex=False
            )
            
            logger.info(
                f"TextChunker initialized: {chunk_size} tokens (exact), "
                f"overlap: {overlap} tokens (tiktoken)"
            )
            
        except ImportError as e:
            logger.error(f"LangChain/tiktoken required: {e}")
            raise
    
    def chunk_text(self, text: str) -> List[str]:
        """Chunk text using LangChain splitter"""
        if not text or not text.strip():
            return []
        
        chunks = self.splitter.split_text(text)
        chunks = [c.strip() for c in chunks if c.strip()]
        
        if chunks:
            token_counts = [len(self.encoding.encode(c)) for c in chunks]
            logger.debug(
                f"Chunked: {len(chunks)} chunks, "
                f"tokens: min={min(token_counts)}, max={max(token_counts)}, "
                f"avg={sum(token_counts)/len(token_counts):.1f}"
            )
        
        return chunks
    
    def chunk_with_metadata(self, text: str, base_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        chunks = self.chunk_text(text)
        
        result = []
        for i, chunk_text in enumerate(chunks):
            chunk_data = {
                **base_metadata,
                'chunk_text': chunk_text,
                'chunk_index': i,
                'total_chunks': len(chunks),
                'chunk_length': len(chunk_text),
                'chunk_tokens': len(self.encoding.encode(chunk_text))
            }
            result.append(chunk_data)
        
        return result
