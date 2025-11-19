# tests/conftest.py
"""Pytest configuration and fixtures"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_text():
    """Sample text for testing chunking"""
    return """
    Apple Inc. designs, manufactures and markets smartphones, personal computers,
    tablets, wearables and accessories. The Company's products include iPhone, Mac,
    iPad, and Wearables. Apple is headquartered in Cupertino, California.
    """


@pytest.fixture
def sample_sec_metadata():
    """Sample SEC metadata for testing"""
    return {
        'ticker': 'AAPL',
        'company_name': 'Apple Inc.',
        'filing_type': '10-K',
        'fiscal_year': 2024,
        'accession_number': '0000320193-24-000001',
        'section': '1A',
        'filing_url': 'https://sec.gov/example',
        'source_type': 'sec_filing'
    }


@pytest.fixture
def sample_chunks():
    """Sample chunks for testing"""
    return [
        "This is the first chunk of text.",
        "This is the second chunk of text.",
        "This is the third chunk of text."
    ]
