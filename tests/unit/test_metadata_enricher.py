# tests/unit/test_metadata_enricher.py
"""Minimal tests for MetadataEnricher"""

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data_processing.metadata_enricher import MetadataEnricher


def test_metadata_enricher_init():
    """Test metadata enricher initialization"""
    enricher = MetadataEnricher()
    assert enricher is not None


def test_generate_chunk_id_sec(sample_sec_metadata):
    """Test SEC chunk ID generation"""
    chunk_id = MetadataEnricher.generate_chunk_id(
        source_metadata=sample_sec_metadata,
        position=0,
        chunk_type="text"
    )
    assert "AAPL" in chunk_id
    assert "10K" in chunk_id
    assert "2024" in chunk_id
    assert "1A" in chunk_id
    assert "text" in chunk_id


def test_enrich_chunk(sample_sec_metadata):
    """Test single chunk enrichment"""
    enricher = MetadataEnricher()
    enriched = enricher.enrich_chunk(
        chunk_text="This is a test chunk.",
        source_metadata=sample_sec_metadata,
        position=0,
        chunk_type="text"
    )
    assert 'chunk_id' in enriched
    assert 'text' in enriched
    assert 'metadata' in enriched
    assert enriched['text'] == "This is a test chunk."


def test_enrich_chunks(sample_chunks, sample_sec_metadata):
    """Test multiple chunks enrichment"""
    enricher = MetadataEnricher()
    enriched_chunks = enricher.enrich_chunks(
        chunks=sample_chunks,
        source_metadata=sample_sec_metadata,
        chunk_type="text"
    )
    assert len(enriched_chunks) == len(sample_chunks)
    assert all('chunk_id' in chunk for chunk in enriched_chunks)


def test_create_source_metadata_sec():
    """Test SEC source metadata creation"""
    metadata = MetadataEnricher.create_source_metadata_sec(
        ticker='AAPL',
        filing_type='10-K',
        filing_date='2024-01-15',
        fiscal_year=2024,
        accession_number='0000320193-24-000001',
        section='1A',
        filing_url='https://sec.gov/test'
    )
    assert metadata['ticker'] == 'AAPL'
    assert metadata['filing_type'] == '10-K'
    assert metadata['source_type'] == 'sec_filing'
