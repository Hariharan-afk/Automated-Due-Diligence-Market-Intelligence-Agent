# src/data_processing/chunking_engine.py
"""
Unified chunking engine supporting multiple data sources

Supports:
- SEC filings: Section-aware chunking with different sizes per section
- Wikipedia: Standard token-based chunking
- News: Standard token-based chunking
"""

from typing import List, Dict, Any, Optional
import re
import tiktoken

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ChunkingEngine:
    """
    Universal chunking engine for all data sources

    Features:
    - Source-aware chunking (SEC, Wikipedia, News)
    - Token-based with tiktoken (accurate)
    - Section-specific sizes for SEC filings
    - Sentence boundary preservation
    - Configurable overlap
    - Context headers for better retrieval
    """

    def __init__(self, encoding_name: str = "cl100k_base"):
        """
        Initialize chunking engine

        Args:
            encoding_name: Tokenizer encoding (default: cl100k_base for GPT models)
        """
        # Initialize tokenizer (accurate token counting)
        self.tokenizer = tiktoken.get_encoding(encoding_name)

        # Load section-specific configurations for SEC
        try:
            self.sec_chunking_config = config.sections_config.get('chunking_strategy', {})
        except:
            self.sec_chunking_config = {}
            logger.warning("sections_config not loaded, using defaults for SEC")

        # Default configurations
        self.default_chunk_size = config.pipeline.chunk_size
        self.default_overlap = config.pipeline.chunk_overlap

        logger.info(
            f"ChunkingEngine initialized "
            f"(default: {self.default_chunk_size} tokens, "
            f"overlap: {self.default_overlap} tokens)"
        )

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken

        Args:
            text: Text to count

        Returns:
            Number of tokens
        """
        return len(self.tokenizer.encode(text))

    def chunk_text(
        self,
        text: str,
        source_type: str = "general",
        section_code: Optional[str] = None,
        section_name: Optional[str] = None,
        preserve_sentences: bool = True
    ) -> List[str]:
        """
        Universal text chunking for all source types

        Args:
            text: Text to chunk
            source_type: 'sec', 'wikipedia', 'news', or 'general'
            section_code: Section code for SEC (e.g., '1A', '7')
            section_name: Section name for context header
            preserve_sentences: Whether to respect sentence boundaries

        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for chunking")
            return []

        # Get appropriate chunk configuration
        chunk_size, chunk_overlap = self._get_chunk_config(source_type, section_code)

        # Create context header
        header = self._create_header(source_type, section_code, section_name)

        # Perform chunking
        chunks = self._chunk_with_config(
            text=text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            header=header,
            preserve_sentences=preserve_sentences
        )

        logger.info(
            f"Created {len(chunks)} chunks for {source_type} "
            f"(section: {section_code or 'N/A'}, "
            f"avg tokens: {sum(self.count_tokens(c) for c in chunks) // len(chunks) if chunks else 0})"
        )

        return chunks

    def chunk_with_metadata(
        self,
        text: str,
        source_type: str = "general",
        section_code: Optional[str] = None,
        section_name: Optional[str] = None,
        base_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Chunk text and return with metadata

        Args:
            text: Text to chunk
            source_type: 'sec', 'wikipedia', 'news', or 'general'
            section_code: Section code (for SEC)
            section_name: Section name
            base_metadata: Base metadata to attach

        Returns:
            List of chunk dicts with text and metadata
        """
        text_chunks = self.chunk_text(
            text=text,
            source_type=source_type,
            section_code=section_code,
            section_name=section_name
        )

        chunks_with_metadata = []
        for i, chunk_text in enumerate(text_chunks):
            chunk_dict = {
                "text": chunk_text,
                "position": i,
                "token_count": self.count_tokens(chunk_text),
                "word_count": len(chunk_text.split()),
                "source_type": source_type,
            }

            # Add section info for SEC
            if source_type == "sec" and section_code:
                chunk_dict["section_code"] = section_code
                if section_name:
                    chunk_dict["section_name"] = section_name

            # Add base metadata if provided
            if base_metadata:
                chunk_dict["metadata"] = base_metadata.copy()
                chunk_dict["metadata"]["chunk_position"] = i

            chunks_with_metadata.append(chunk_dict)

        return chunks_with_metadata

    def _get_chunk_config(
        self,
        source_type: str,
        section_code: Optional[str] = None
    ) -> tuple:
        """
        Get chunk size and overlap for source type

        Args:
            source_type: Source type ('sec', 'wikipedia', 'news')
            section_code: SEC section code (if applicable)

        Returns:
            Tuple of (chunk_size, chunk_overlap)
        """
        if source_type == "sec" and section_code:
            # Use section-specific config for SEC
            section_config = self.sec_chunking_config.get(section_code)

            if section_config:
                return (
                    section_config.get('chunk_size', self.default_chunk_size),
                    section_config.get('chunk_overlap', self.default_overlap)
                )

            # Fallback to SEC default
            default_sec = self.sec_chunking_config.get('default', {})
            return (
                default_sec.get('chunk_size', self.default_chunk_size),
                default_sec.get('chunk_overlap', self.default_overlap)
            )

        # For Wikipedia, News, and general text
        return (self.default_chunk_size, self.default_overlap)

    def _create_header(
        self,
        source_type: str,
        section_code: Optional[str],
        section_name: Optional[str]
    ) -> str:
        """
        Create context header for chunks

        Args:
            source_type: Source type
            section_code: Section code
            section_name: Section name

        Returns:
            Header string
        """
        if source_type == "sec" and section_code and section_name:
            return f"[SEC Filing - Section {section_code}: {section_name}]\n\n"
        elif source_type == "sec" and section_code:
            return f"[SEC Filing - Section {section_code}]\n\n"
        elif source_type == "wikipedia":
            return "[Wikipedia]\n\n"
        elif source_type == "news":
            return "[News Article]\n\n"
        else:
            return ""

    def _chunk_with_config(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
        header: str,
        preserve_sentences: bool
    ) -> List[str]:
        """
        Perform the actual chunking with given configuration

        Args:
            text: Text to chunk
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap in tokens
            header: Header to prepend
            preserve_sentences: Whether to preserve sentence boundaries

        Returns:
            List of text chunks
        """
        # Split into sentences if preserving boundaries
        if preserve_sentences:
            sentences = self._split_into_sentences(text)
        else:
            sentences = [text]

        chunks = []
        current_chunk = []
        current_tokens = 0

        # Account for header tokens
        header_tokens = self.count_tokens(header) if header else 0
        available_tokens = chunk_size - header_tokens

        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)

            # If adding this sentence exceeds chunk size, create new chunk
            if current_tokens + sentence_tokens > available_tokens and current_chunk:
                # Create chunk from current sentences
                chunk_text = header + " ".join(current_chunk)
                chunks.append(chunk_text)

                # Start new chunk with overlap
                overlap_sentences = self._get_overlap_sentences(
                    current_chunk,
                    chunk_overlap
                )

                current_chunk = overlap_sentences
                current_tokens = sum(
                    self.count_tokens(s) for s in current_chunk
                )

            # Add sentence to current chunk
            current_chunk.append(sentence)
            current_tokens += sentence_tokens

        # Add remaining text as final chunk
        if current_chunk:
            chunk_text = header + " ".join(current_chunk)
            chunks.append(chunk_text)

        return chunks

    @staticmethod
    def _split_into_sentences(text: str) -> List[str]:
        """
        Split text into sentences

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        # Replace common abbreviations to avoid false splits
        replacements = {
            "Mr.": "Mr", "Mrs.": "Mrs", "Dr.": "Dr",
            "Inc.": "Inc", "Corp.": "Corp", "Ltd.": "Ltd",
            "U.S.": "US", "e.g.": "eg", "i.e.": "ie",
            "vs.": "vs", "etc.": "etc"
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # Filter empty and strip
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences

    def _get_overlap_sentences(
        self,
        sentences: List[str],
        overlap_tokens: int
    ) -> List[str]:
        """
        Get last few sentences for overlap

        Args:
            sentences: List of sentences
            overlap_tokens: Target overlap size in tokens

        Returns:
            List of sentences for overlap
        """
        if not sentences:
            return []

        overlap_sentences = []
        token_count = 0

        # Work backwards from end
        for sentence in reversed(sentences):
            sentence_tokens = self.count_tokens(sentence)

            if token_count + sentence_tokens > overlap_tokens:
                break

            overlap_sentences.insert(0, sentence)
            token_count += sentence_tokens

        return overlap_sentences

    def get_chunk_stats(self, chunks: List[str]) -> Dict[str, int]:
        """
        Get statistics about generated chunks

        Args:
            chunks: List of chunks

        Returns:
            Statistics dictionary
        """
        if not chunks:
            return {
                'count': 0,
                'avg_tokens': 0,
                'min_tokens': 0,
                'max_tokens': 0,
                'total_tokens': 0
            }

        token_counts = [self.count_tokens(chunk) for chunk in chunks]

        return {
            'count': len(chunks),
            'avg_tokens': sum(token_counts) // len(token_counts),
            'min_tokens': min(token_counts),
            'max_tokens': max(token_counts),
            'total_tokens': sum(token_counts)
        }
