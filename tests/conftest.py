"""
Pytest configuration file for test discovery and fixtures.
This file ensures proper import paths and provides shared fixtures.
"""

import sys
import os
from pathlib import Path

# Add project root to Python path (so we can import src.module)
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Also add src directory for direct imports (backward compatibility)
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pytest


@pytest.fixture(scope="session")
def project_root_dir():
    """Return the project root directory path."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def src_dir():
    """Return the source code directory path."""
    return Path(__file__).parent.parent / "src"


@pytest.fixture(scope="session")
def tests_dir():
    """Return the tests directory path."""
    return Path(__file__).parent


@pytest.fixture(scope="session")
def data_dir():
    """Return the data directory path."""
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def sample_company_data():
    """Provide sample company data for testing."""
    return {
        "company_name": "Apple Inc.",
        "ticker": "AAPL",
        "industry": "Technology",
        "founded": "1976",
        "headquarters": "Cupertino, California"
    }


@pytest.fixture
def sample_wikipedia_text():
    """Provide sample Wikipedia text for testing."""
    return """
    Apple Inc. is an American multinational technology company headquartered in Cupertino, California.
    Apple is the world's largest technology company by revenue, with US$394.3 billion in 2022.
    As of March 2023, Apple is the world's biggest company by market capitalization.

    ##TABLE_START##
    | Year | Revenue | Employees |
    |------|---------|-----------|
    | 2020 | $274.5B | 147,000   |
    | 2021 | $365.8B | 154,000   |
    | 2022 | $394.3B | 164,000   |
    ##TABLE_END##

    Apple was founded by Steve Jobs, Steve Wozniak, and Ronald Wayne in April 1976.
    """


@pytest.fixture
def sample_news_article():
    """Provide sample news article for testing."""
    return {
        "title": "Apple Announces New Product Line",
        "description": "Apple Inc. unveiled its latest innovations in a keynote event.",
        "content": "Apple Inc. announced several new products today, including updates to its iPhone and Mac lineups.",
        "author": "Tech Reporter",
        "publishedAt": "2023-10-15T10:00:00Z",
        "source": {"id": "techcrunch", "name": "TechCrunch"},
        "url": "https://example.com/article"
    }


@pytest.fixture
def sample_sec_filing():
    """Provide sample SEC filing data for testing."""
    return {
        "ticker": "AAPL",
        "filing_type": "10-K",
        "filing_date": "2023-10-27",
        "sections": {
            "business": "Apple Inc. designs, manufactures, and markets smartphones...",
            "risk_factors": "The Company's business can be impacted by various risks...",
            "financial_data": "##TABLE_START##\n| Metric | 2023 | 2022 |\n|--------|------|------|\n| Revenue | 394B | 365B |\n##TABLE_END##"
        }
    }


@pytest.fixture
def mock_database_connection(monkeypatch):
    """Mock database connection for testing."""
    class MockConnection:
        def __init__(self):
            self.is_connected = True
            self.data_store = {}

        def execute(self, query, params=None):
            return {"status": "success", "rows": []}

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            self.is_connected = False

    return MockConnection()


@pytest.fixture
def mock_api_response():
    """Mock API response for testing."""
    return {
        "status": "ok",
        "totalResults": 100,
        "articles": [
            {
                "title": "Test Article",
                "content": "Test content",
                "publishedAt": "2023-10-15T10:00:00Z"
            }
        ]
    }
