"""
Unit tests for SEC Fetcher module
"""

import pytest
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sec_fetcher import SECFetcher


class TestSECFetcher:
    """Test SEC Fetcher functionality"""

    def test_init_without_api_key(self):
        """Test initialization without API key"""
        fetcher = SECFetcher(api_key=None)
        assert fetcher.api_key is None
        assert fetcher.config is not None

    def test_init_with_api_key(self):
        """Test initialization with API key"""
        fetcher = SECFetcher(api_key="test_key_123")
        assert fetcher.api_key == "test_key_123"

    def test_ticker_lookup_structure(self):
        """Test ticker lookup file structure"""
        ticker_file = "data/company_tickers.json"
        if os.path.exists(ticker_file):
            with open(ticker_file, 'r') as f:
                tickers = json.load(f)
            assert isinstance(tickers, dict)
            assert len(tickers) > 0

            # Check first entry structure
            first_key = list(tickers.keys())[0]
            first_entry = tickers[first_key]
            assert 'ticker' in first_entry
            assert 'cik_str' in first_entry or 'cik' in first_entry
        else:
            pytest.skip(f"Ticker file not found: {ticker_file}")

    def test_cik_formatting(self):
        """Test CIK number formatting"""
        test_cases = [
            ("320193", "0000320193"),
            ("0000320193", "0000320193"),
            ("789019", "0000789019"),
            ("1318605", "0001318605"),
        ]

        for input_cik, expected in test_cases:
            formatted = input_cik.zfill(10)
            assert formatted == expected

    def test_section_configuration(self):
        """Test filing sections configuration"""
        fetcher = SECFetcher(api_key="test")

        assert '10-K' in fetcher.SECTIONS
        assert '10-Q' in fetcher.SECTIONS

        assert fetcher.SECTIONS['10-K'] == ['1', '1A', '7', '8']
        assert fetcher.SECTIONS['10-Q'] == ['part1item1', 'part1item2', 'part2item1a']

    def test_cache_enabled_default(self):
        """Test that caching is enabled by default"""
        fetcher = SECFetcher(api_key="test")
        assert hasattr(fetcher, 'config')
        assert fetcher.config.sec_api.cache_enabled == True

    def test_rate_limit_configuration(self):
        """Test rate limiting configuration"""
        fetcher = SECFetcher(api_key="test")
        assert fetcher.config.sec_api.rate_limit.calls_per_minute == 10

    @pytest.mark.parametrize("filing_type,expected_sections", [
        ("10-K", 4),
        ("10-Q", 3),
    ])
    def test_expected_section_counts(self, filing_type, expected_sections):
        """Test expected section counts for different filing types"""
        fetcher = SECFetcher(api_key="test")
        assert len(fetcher.SECTIONS[filing_type]) == expected_sections


class TestSECFilingValidation:
    """Test SEC filing data validation"""

    def test_filing_data_structure(self):
        """Test filing data structure validation"""
        required_fields = [
            'ticker', 'company_name', 'cik', 'filing_type',
            'filing_date', 'accession_number', 'sections'
        ]

        # Mock filing data
        mock_filing = {
            'ticker': 'AAPL',
            'company_name': 'Apple Inc.',
            'cik': '0000320193',
            'filing_type': '10-K',
            'filing_date': '2024-10-26',
            'accession_number': '0000320193-24-000001',
            'sections': {'1': 'Business section text'}
        }

        for field in required_fields:
            assert field in mock_filing

    def test_sections_is_dict(self):
        """Test that sections field is a dictionary"""
        mock_sections = {
            '1': 'Business text',
            '1A': 'Risk factors text',
            '7': 'MD&A text',
            '8': 'Financial statements text'
        }

        assert isinstance(mock_sections, dict)
        assert len(mock_sections) == 4
        assert all(isinstance(v, str) for v in mock_sections.values())


class TestTableMarkers:
    """Test table marker handling"""

    def test_table_markers_in_text(self):
        """Test detection of table markers"""
        text_with_table = """
Some text before table.

##TABLE_START
2024  Change  2023
100   10%     90
##TABLE_END

Some text after table.
"""
        assert '##TABLE_START' in text_with_table
        assert '##TABLE_END' in text_with_table

    def test_count_tables(self):
        """Test counting tables in text"""
        text = """
##TABLE_START
Table 1 data
##TABLE_END

Some text

##TABLE_START
Table 2 data
##TABLE_END
"""
        table_count = text.count('##TABLE_START')
        assert table_count == 2


# Pytest configuration
def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (deselect with '-m \"not integration\"')"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
