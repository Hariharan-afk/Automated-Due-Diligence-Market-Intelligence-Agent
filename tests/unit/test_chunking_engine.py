# tests/unit/test_chunking_engine.py
"""Minimal tests for ChunkingEngine"""

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data_processing.chunking_engine import ChunkingEngine


def test_chunking_engine_init():
    """Test chunking engine initialization"""
    engine = ChunkingEngine()
    assert engine is not None
    assert engine.default_chunk_size > 0
    assert engine.default_overlap > 0


def test_count_tokens(sample_text):
    """Test token counting"""
    engine = ChunkingEngine()
    token_count = engine.count_tokens(sample_text)
    assert token_count > 0
    assert isinstance(token_count, int)


def test_chunk_text_general(sample_text):
    """Test basic text chunking"""
    engine = ChunkingEngine()
    chunks = engine.chunk_text(sample_text, source_type="general")
    assert len(chunks) > 0
    assert all(isinstance(chunk, str) for chunk in chunks)


def test_chunk_text_sec(sample_text):
    """Test SEC section-aware chunking"""
    engine = ChunkingEngine()
    chunks = engine.chunk_text(
        sample_text,
        source_type="sec",
        section_code="1A",
        section_name="Risk Factors"
    )
    assert len(chunks) > 0
    assert "[SEC Filing" in chunks[0]  # Check for header


def test_chunk_with_metadata(sample_text, sample_sec_metadata):
    """Test chunking with metadata"""
    engine = ChunkingEngine()
    chunks = engine.chunk_with_metadata(
        text=sample_text,
        source_type="sec",
        section_code="1A",
        base_metadata=sample_sec_metadata
    )
    assert len(chunks) > 0
    assert all('text' in chunk for chunk in chunks)
    assert all('position' in chunk for chunk in chunks)
    assert all('token_count' in chunk for chunk in chunks)


def test_get_chunk_stats(sample_chunks):
    """Test chunk statistics"""
    engine = ChunkingEngine()
    stats = engine.get_chunk_stats(sample_chunks)
    assert stats['count'] == len(sample_chunks)
    assert stats['total_tokens'] > 0
    assert stats['avg_tokens'] > 0
