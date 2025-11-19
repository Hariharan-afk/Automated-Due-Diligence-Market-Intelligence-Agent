# tests/integration/test_sec_pipeline.py
"""Minimal integration test for SEC pipeline components"""

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data_processing.chunking_engine import ChunkingEngine
from src.data_processing.metadata_enricher import MetadataEnricher


def test_sec_pipeline_integration(sample_text, sample_sec_metadata):
    """Test complete SEC processing workflow"""
    # Step 1: Chunk text
    chunker = ChunkingEngine()
    chunks = chunker.chunk_text(
        text=sample_text,
        source_type='sec',
        section_code='1A',
        section_name='Risk Factors'
    )
    assert len(chunks) > 0

    # Step 2: Enrich with metadata
    enricher = MetadataEnricher()
    enriched_chunks = enricher.enrich_chunks(
        chunks=chunks,
        source_metadata=sample_sec_metadata
    )
    assert len(enriched_chunks) == len(chunks)

    # Step 3: Verify structure
    for chunk in enriched_chunks:
        assert 'chunk_id' in chunk
        assert 'text' in chunk
        assert 'metadata' in chunk
        assert 'AAPL' in chunk['chunk_id']


def test_chunking_stats_integration(sample_text):
    """Test chunk statistics generation"""
    chunker = ChunkingEngine()
    chunks = chunker.chunk_text(sample_text, source_type="general")
    stats = chunker.get_chunk_stats(chunks)

    assert stats['count'] == len(chunks)
    assert stats['total_tokens'] > 0
