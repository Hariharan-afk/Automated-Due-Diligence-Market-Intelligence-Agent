"""
Unit Tests for Data Pipeline - FINAL VERSION
Testing data acquisition, preprocessing, and validation
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import json

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_acquisition import CompanyTickerMatcher, WikipediaDataFetcher, NewsAPIFetcher
from data_preprocessing import DataCleaner, WikipediaPreprocessor, NewsPreprocessor
from schema_validator import SchemaValidator, AnomalyDetector


class TestCompanyTickerMatcher(unittest.TestCase):
    """Test ticker matching functionality"""
    
    def setUp(self):
        # Create mock ticker data
        self.mock_ticker_data = pd.DataFrame({
            'symbol': ['AAPL', 'GOOGL', 'MSFT'],
            'name': ['Apple Inc', 'Alphabet Inc', 'Microsoft Corporation'],
            'exchange': ['NASDAQ', 'NASDAQ', 'NASDAQ']
        })
    
    @patch('pandas.read_csv')
    def test_load_tickers(self, mock_read_csv):
        """Test ticker file loading"""
        mock_read_csv.return_value = self.mock_ticker_data
        
        matcher = CompanyTickerMatcher()
        self.assertIsNotNone(matcher.ticker_df)
        self.assertEqual(len(matcher.ticker_df), 3)
    
    @patch('pandas.read_csv')
    def test_match_by_ticker(self, mock_read_csv):
        """Test matching by ticker symbol"""
        mock_read_csv.return_value = self.mock_ticker_data
        
        matcher = CompanyTickerMatcher()
        ticker, name, cik = matcher.match_company("AAPL")
        
        self.assertEqual(ticker, "AAPL")
        self.assertEqual(name, "Apple Inc")
    
    @patch('pandas.read_csv')
    def test_match_by_name(self, mock_read_csv):
        """Test matching by company name"""
        mock_read_csv.return_value = self.mock_ticker_data
        
        matcher = CompanyTickerMatcher()
        ticker, name, cik = matcher.match_company("Apple")
        
        self.assertEqual(ticker, "AAPL")
        self.assertIn("Apple", name)
    
    @patch('pandas.read_csv')
    def test_no_match(self, mock_read_csv):
        """Test behavior when no match found"""
        mock_read_csv.return_value = self.mock_ticker_data
        
        matcher = CompanyTickerMatcher()
        ticker, name, cik = matcher.match_company("NonexistentCompany")
        
        self.assertIsNone(ticker)
        self.assertEqual(name, "NonexistentCompany")


class TestDataCleaner(unittest.TestCase):
    """Test data cleaning functions"""
    
    def test_clean_text_basic(self):
        """Test basic text cleaning"""
        dirty_text = "  Hello   World!  "
        clean_text = DataCleaner.clean_text(dirty_text)
        self.assertEqual(clean_text, "Hello World!")
    
    def test_clean_text_html(self):
        """Test HTML tag removal"""
        html_text = "<p>Hello <b>World</b></p>"
        clean_text = DataCleaner.clean_text(html_text)
        self.assertNotIn("<p>", clean_text)
        self.assertNotIn("<b>", clean_text)
    
    def test_clean_text_special_chars(self):
        """Test special character removal"""
        text = "Hello @#$% World!"
        clean_text = DataCleaner.clean_text(text)
        self.assertNotIn("@", clean_text)
        self.assertNotIn("#", clean_text)
    
    def test_clean_text_empty(self):
        """Test handling empty text"""
        self.assertEqual(DataCleaner.clean_text(""), "")
        self.assertEqual(DataCleaner.clean_text("N/A"), "")
        self.assertEqual(DataCleaner.clean_text(None), "")
    
    def test_clean_url(self):
        """Test URL cleaning"""
        url = "example.com/page"
        clean_url = DataCleaner.clean_url(url)
        self.assertTrue(clean_url.startswith("https://"))
    
    def test_clean_url_already_valid(self):
        """Test URL that's already valid"""
        url = "https://example.com"
        clean_url = DataCleaner.clean_url(url)
        self.assertEqual(clean_url, url)
    
    def test_parse_date_iso(self):
        """Test ISO date parsing"""
        date_str = "2024-10-24T12:00:00Z"
        parsed = DataCleaner.parse_date(date_str)
        self.assertEqual(parsed, "2024-10-24")
    
    def test_parse_date_gdelt(self):
        """Test GDELT format date parsing"""
        date_str = "20241024120000"
        parsed = DataCleaner.parse_date(date_str)
        self.assertEqual(parsed, "2024-10-24")
    
    def test_remove_duplicates(self):
        """Test duplicate removal"""
        items = [
            {"url": "http://example1.com", "title": "Article 1"},
            {"url": "http://example2.com", "title": "Article 2"},
            {"url": "http://example1.com", "title": "Article 1 Duplicate"},
        ]
        unique = DataCleaner.remove_duplicates(items)
        self.assertEqual(len(unique), 2)


class TestWikipediaPreprocessor(unittest.TestCase):
    """Test Wikipedia data preprocessing"""
    
    def setUp(self):
        self.processor = WikipediaPreprocessor()
    
    def test_process_valid_data(self):
        """Test processing valid Wikipedia data"""
        wiki_data = {
            "title": "Apple Inc",
            "summary": "Apple is a technology company",
            "full_text": "Apple Inc. is an American multinational technology company.",
            "url": "https://en.wikipedia.org/wiki/Apple_Inc",
            "sections": [{"title": "History", "text": "Founded in 1976"}],
            "timestamp": "2024-10-24T12:00:00"
        }
        
        processed = self.processor.process(wiki_data)
        
        self.assertEqual(processed["title"], "Apple Inc")
        self.assertIn("word_count", processed)
        self.assertIn("section_count", processed)
        self.assertEqual(processed["section_count"], 1)
    
    def test_process_error_data(self):
        """Test processing error data"""
        wiki_data = {"error": "Page not found"}
        processed = self.processor.process(wiki_data)
        self.assertIn("error", processed)


class TestNewsPreprocessor(unittest.TestCase):
    """Test news article preprocessing"""
    
    def setUp(self):
        self.processor = NewsPreprocessor()
    
    def test_process_articles(self):
        """Test processing news articles"""
        articles = [
            {
                "title": "Apple releases new iPhone",
                "url": "https://example.com/article1",
                "source": "TechNews",
                "published_date": "2024-10-24T12:00:00Z",
                "description": "Apple announced...",
                "content": "Full article content here"
            },
            {
                "title": "[Removed]",
                "url": "https://example.com/removed",
                "source": "News",
                "published_date": "2024-10-24",
                "description": "",
                "content": ""
            }
        ]
        
        processed = self.processor.process(articles)
        
        # Should filter out removed article
        self.assertEqual(len(processed), 1)
        self.assertIn("word_count", processed[0])
        self.assertIn("has_content", processed[0])
    
    def test_remove_duplicates(self):
        """Test duplicate article removal"""
        articles = [
            {"title": "Article 1", "url": "https://example.com/1", "source": "A", "published_date": "2024-10-24"},
            {"title": "Article 1", "url": "https://example.com/1", "source": "B", "published_date": "2024-10-24"},
        ]
        
        processed = self.processor.process(articles)
        self.assertEqual(len(processed), 1)


class TestSchemaValidator(unittest.TestCase):
    """Test schema validation"""
    
    def setUp(self):
        self.validator = SchemaValidator()
    
    def test_valid_schema(self):
        """Test validation of valid data"""
        data = {
            "company_name": "Apple Inc",
            "ticker": "AAPL",
            "wikipedia": {
                "title": "Apple Inc",
                "summary": "A technology company",
                "url": "https://en.wikipedia.org/wiki/Apple_Inc"
            },
            "news_articles": [
                {"title": "News 1", "url": "https://example.com/1"}
            ]
        }
        
        result = self.validator.validate(data)
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)
    
    def test_missing_required_field(self):
        """Test validation with missing required field"""
        data = {
            "ticker": "AAPL",
            "wikipedia": {},
            "news_articles": []
        }
        
        result = self.validator.validate(data)
        self.assertFalse(result["valid"])
        self.assertTrue(any("company_name" in error for error in result["errors"]))
    
    def test_wrong_type(self):
        """Test validation with wrong data type"""
        data = {
            "company_name": "Apple Inc",
            "wikipedia": "not a dict",  # Should be dict
            "news_articles": []
        }
        
        result = self.validator.validate(data)
        self.assertFalse(result["valid"])


class TestAnomalyDetector(unittest.TestCase):
    """Test anomaly detection"""
    
    def setUp(self):
        self.detector = AnomalyDetector()
    
    def test_wikipedia_too_short(self):
        """Test detection of short Wikipedia content"""
        data = {
            "company_name": "Test Company",
            "wikipedia": {"word_count": 50},
            "news_articles": [{"title": "Test", "url": "test.com", "word_count": 100, "has_content": True}]
        }
        
        result = self.detector.detect(data)
        self.assertTrue(result["has_anomalies"])
        self.assertTrue(any(a["type"] == "wikipedia_too_short" for a in result["anomalies"]))
    
    def test_insufficient_news(self):
        """Test detection of insufficient news articles"""
        data = {
            "company_name": "Test Company",
            "wikipedia": {"word_count": 1000},
            "news_articles": []
        }
        
        result = self.detector.detect(data)
        self.assertTrue(result["has_anomalies"])
        self.assertTrue(any(a["type"] == "insufficient_news" for a in result["anomalies"]))
    
    def test_no_anomalies(self):
        """Test detection with clean data"""
        data = {
            "company_name": "Test Company",
            "wikipedia": {"word_count": 5000},
            "news_articles": [
                {"title": "Test", "url": "test.com", "word_count": 500, "has_content": True}
                for _ in range(10)
            ],
            "statistics": {
                "date_range": {"latest": "2024-10-24"}
            }
        }
        
        result = self.detector.detect(data)
        self.assertFalse(result["has_anomalies"])


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestCompanyTickerMatcher))
    suite.addTests(loader.loadTestsFromTestCase(TestDataCleaner))
    suite.addTests(loader.loadTestsFromTestCase(TestWikipediaPreprocessor))
    suite.addTests(loader.loadTestsFromTestCase(TestNewsPreprocessor))
    suite.addTests(loader.loadTestsFromTestCase(TestSchemaValidator))
    suite.addTests(loader.loadTestsFromTestCase(TestAnomalyDetector))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success/failure
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)