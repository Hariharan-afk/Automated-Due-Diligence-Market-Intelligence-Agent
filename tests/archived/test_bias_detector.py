"""
Comprehensive unit tests for Bias Detection module.
Tests include edge cases, missing values, anomalies, and fairness metrics.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, mock_open
import json

from src.bias_detector import BiasDetector


class TestBiasDetectorInitialization:
    """Test BiasDetector initialization."""

    def test_init_default_configuration(self):
        """Test detector initializes with correct default configuration."""
        detector = BiasDetector()
        assert detector.slicing_features == ['source', 'published_date', 'fiscal_year', 'filing_type']
        assert detector.sec_expected_sections == {'10-K': 4, '10-Q': 3}

    def test_init_multiple_instances(self):
        """Test multiple detector instances are independent."""
        detector1 = BiasDetector()
        detector2 = BiasDetector()
        assert detector1 is not detector2
        assert detector1.slicing_features == detector2.slicing_features


@pytest.mark.data_quality
class TestAnalyzeDataEdgeCases:
    """Test analyze_data method with edge cases."""

    def test_analyze_empty_data(self):
        """Test analysis with completely empty data."""
        detector = BiasDetector()
        result = detector.analyze_data({})
        assert result["error"] == "No data to analyze"
        assert result["bias_detected"] is False

    def test_analyze_no_news_no_sec(self):
        """Test analysis with company name but no content."""
        detector = BiasDetector()
        data = {"company_name": "Test Corp", "news_articles": [], "sec_filings": {}}
        result = detector.analyze_data(data)
        assert result["error"] == "No data to analyze"

    def test_analyze_only_news_articles(self):
        """Test analysis with only news articles, no SEC data."""
        detector = BiasDetector()
        data = {
            "company_name": "Apple Inc.",
            "news_articles": [
                {"source": "TechCrunch", "published_date": "2023-10-15", "word_count": 500},
                {"source": "TechCrunch", "published_date": "2023-10-16", "word_count": 600},
            ],
            "sec_filings": {}
        }
        result = detector.analyze_data(data)
        assert result["company_name"] == "Apple Inc."
        assert result["total_articles"] == 2
        assert "news" in result["analysis"]
        assert result["total_sec_filings"] == 0

    def test_analyze_only_sec_filings(self):
        """Test analysis with only SEC filings, no news."""
        detector = BiasDetector()
        data = {
            "company_name": "Apple Inc.",
            "news_articles": [],
            "sec_filings": {
                "10-K": {
                    "fiscal_year": "2023",
                    "sections": {"business": "content", "risk": "content", "md&a": "content", "financials": "content"},
                    "statistics": {"total_words": 50000}
                }
            }
        }
        result = detector.analyze_data(data)
        assert result["total_articles"] == 0
        assert result["total_sec_filings"] == 1
        assert "sec" in result["analysis"]

    def test_analyze_with_error_sec_filings(self):
        """Test handling of SEC filings with errors."""
        detector = BiasDetector()
        data = {
            "company_name": "Test Corp",
            "news_articles": [{"source": "Test", "published_date": "2023-10-15", "word_count": 100}],
            "sec_filings": {
                "10-K": {"error": "Failed to fetch"},
                "10-Q": {"error": "Not found"}
            }
        }
        result = detector.analyze_data(data)
        assert result["total_sec_filings"] == 0  # Error filings don't count


@pytest.mark.data_quality
class TestSourceAnalysisEdgeCases:
    """Test _analyze_by_source with edge cases."""

    def test_source_analysis_single_source(self):
        """Test with all articles from single source (100% dominance)."""
        detector = BiasDetector()
        df = pd.DataFrame([
            {"source": "TechCrunch", "published_date": "2023-10-15", "word_count": 500},
            {"source": "TechCrunch", "published_date": "2023-10-16", "word_count": 600},
            {"source": "TechCrunch", "published_date": "2023-10-17", "word_count": 700},
        ])
        result = detector._analyze_by_source(df)
        assert result["total_sources"] == 1
        assert result["dominance_ratio"] == 1.0  # 100% dominance
        assert result["distribution"]["TechCrunch"] == 3

    def test_source_analysis_balanced_sources(self):
        """Test with perfectly balanced sources."""
        detector = BiasDetector()
        df = pd.DataFrame([
            {"source": "Source A", "published_date": "2023-10-15", "word_count": 500},
            {"source": "Source B", "published_date": "2023-10-16", "word_count": 600},
            {"source": "Source C", "published_date": "2023-10-17", "word_count": 700},
        ])
        result = detector._analyze_by_source(df)
        assert result["total_sources"] == 3
        assert result["dominance_ratio"] == pytest.approx(1/3, abs=0.01)

    def test_source_analysis_empty_dataframe(self):
        """Test with empty DataFrame."""
        detector = BiasDetector()
        df = pd.DataFrame(columns=["source", "published_date", "word_count"])
        result = detector._analyze_by_source(df)
        assert result["total_sources"] == 0
        assert result["dominance_ratio"] == 0
        assert result["percentages"] == {}

    def test_source_analysis_missing_source_column(self):
        """Test handling of missing source column."""
        detector = BiasDetector()
        df = pd.DataFrame([{"published_date": "2023-10-15", "word_count": 500}])
        with pytest.raises(KeyError):
            detector._analyze_by_source(df)

    def test_source_analysis_null_sources(self):
        """Test handling of null/NaN source values."""
        detector = BiasDetector()
        df = pd.DataFrame([
            {"source": "TechCrunch", "published_date": "2023-10-15", "word_count": 500},
            {"source": None, "published_date": "2023-10-16", "word_count": 600},
            {"source": np.nan, "published_date": "2023-10-17", "word_count": 700},
        ])
        result = detector._analyze_by_source(df)
        # NaN values should be counted separately
        assert result["total_sources"] >= 1


@pytest.mark.data_quality
class TestTemporalAnalysisEdgeCases:
    """Test _analyze_by_time with edge cases."""

    def test_temporal_analysis_no_valid_dates(self):
        """Test with all invalid/unparseable dates."""
        detector = BiasDetector()
        df = pd.DataFrame([
            {"source": "Test", "published_date": "invalid-date", "word_count": 500},
            {"source": "Test", "published_date": "not-a-date", "word_count": 600},
        ])
        result = detector._analyze_by_time(df)
        assert "error" in result
        assert result["recency_bias"] == 0.0

    def test_temporal_analysis_null_dates(self):
        """Test with null/None dates."""
        detector = BiasDetector()
        df = pd.DataFrame([
            {"source": "Test", "published_date": None, "word_count": 500},
            {"source": "Test", "published_date": np.nan, "word_count": 600},
        ])
        result = detector._analyze_by_time(df)
        assert "error" in result

    def test_temporal_analysis_single_date(self):
        """Test with all articles from same date."""
        detector = BiasDetector()
        df = pd.DataFrame([
            {"source": "Test1", "published_date": "2023-10-15", "word_count": 500},
            {"source": "Test2", "published_date": "2023-10-15", "word_count": 600},
        ])
        result = detector._analyze_by_time(df)
        assert result["date_range"]["earliest"] == result["date_range"]["latest"]

    def test_temporal_analysis_wide_date_range(self):
        """Test with very wide date range (multiple years)."""
        detector = BiasDetector()
        df = pd.DataFrame([
            {"source": "Test", "published_date": "2020-01-01", "word_count": 500},
            {"source": "Test", "published_date": "2023-12-31", "word_count": 600},
        ])
        result = detector._analyze_by_time(df)
        assert "date_range" in result
        assert result["date_range"]["earliest"] == "2020-01-01"
        assert result["date_range"]["latest"] == "2023-12-31"

    def test_temporal_analysis_future_dates(self):
        """Test with future dates."""
        detector = BiasDetector()
        future_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
        df = pd.DataFrame([
            {"source": "Test", "published_date": future_date, "word_count": 500},
        ])
        result = detector._analyze_by_time(df)
        # Should still process, not raise error
        assert "date_range" in result


@pytest.mark.data_quality
class TestQualityAnalysisEdgeCases:
    """Test _analyze_quality_across_slices with edge cases."""

    def test_quality_analysis_missing_word_count_column(self):
        """Test when word_count column is missing."""
        detector = BiasDetector()
        df = pd.DataFrame([
            {"source": "Test", "published_date": "2023-10-15"},
        ])
        result = detector._analyze_quality_across_slices(df)
        assert result["mean_word_count"] == 0.0
        assert result["std_word_count"] == 0.0

    def test_quality_analysis_zero_word_counts(self):
        """Test with all zero word counts."""
        detector = BiasDetector()
        df = pd.DataFrame([
            {"source": "Test1", "word_count": 0},
            {"source": "Test2", "word_count": 0},
        ])
        result = detector._analyze_quality_across_slices(df)
        assert result["mean_word_count"] == 0.0
        assert result["std_word_count"] == 0.0

    def test_quality_analysis_extreme_word_counts(self):
        """Test with extreme word count values."""
        detector = BiasDetector()
        df = pd.DataFrame([
            {"source": "Test1", "word_count": 1},
            {"source": "Test2", "word_count": 1000000},
        ])
        result = detector._analyze_quality_across_slices(df)
        assert result["mean_word_count"] > 0
        assert result["std_word_count"] > 0

    def test_quality_analysis_null_word_counts(self):
        """Test with null/NaN word counts."""
        detector = BiasDetector()
        df = pd.DataFrame([
            {"source": "Test1", "word_count": 500},
            {"source": "Test2", "word_count": None},
            {"source": "Test3", "word_count": np.nan},
        ])
        result = detector._analyze_quality_across_slices(df)
        # Should handle NaN gracefully
        assert isinstance(result["mean_word_count"], (int, float))


@pytest.mark.edge_case
class TestSECAnalysisEdgeCases:
    """Test SEC-specific analysis with edge cases."""

    def test_sec_fiscal_years_no_years(self):
        """Test with SEC data but no fiscal years."""
        detector = BiasDetector()
        sec = {"10-K": {"sections": {}}, "10-Q": {"sections": {}}}
        result = detector._analyze_sec_fiscal_years(sec)
        assert "error" in result
        assert result["is_continuous"] is True

    def test_sec_fiscal_years_discontinuous(self):
        """Test with non-continuous fiscal years."""
        detector = BiasDetector()
        sec = {
            "10-K": {"fiscal_year": "2020"},
            "10-Q": {"fiscal_year": "2023"},  # Gap: 2021, 2022 missing
        }
        result = detector._analyze_sec_fiscal_years(sec)
        assert result["is_continuous"] is False

    def test_sec_filing_types_no_valid_filings(self):
        """Test with all error filings."""
        detector = BiasDetector()
        sec = {
            "10-K": {"error": "Failed"},
            "10-Q": {"error": "Not found"},
        }
        result = detector._analyze_sec_filing_types(sec)
        assert result["types_available"] == []
        assert result["has_10k"] is False
        assert result["has_10q"] is False
        assert result["has_both"] is False

    def test_sec_sections_missing_sections_key(self):
        """Test section analysis when sections key is missing."""
        detector = BiasDetector()
        sec = {"10-K": {"fiscal_year": "2023"}}  # No sections key
        result = detector._analyze_sec_sections(sec)
        assert "10-K" in result
        assert result["10-K"]["actual"] == 0

    def test_sec_sections_incomplete_coverage(self):
        """Test with incomplete section coverage."""
        detector = BiasDetector()
        sec = {
            "10-K": {
                "sections": {"business": "content", "risk": "content"}  # Expected 4, got 2
            }
        }
        result = detector._analyze_sec_sections(sec)
        assert result["10-K"]["completeness_ratio"] == 0.5

    def test_sec_complexity_no_statistics(self):
        """Test complexity analysis with no statistics."""
        detector = BiasDetector()
        sec = {"10-K": {"sections": {}}}  # No statistics key
        result = detector._analyze_sec_complexity(sec)
        assert result == {}


@pytest.mark.unit
class TestFairnessMetrics:
    """Test fairness metric calculations."""

    def test_fairness_metrics_empty_inputs(self):
        """Test fairness calculation with empty inputs."""
        detector = BiasDetector()
        result = detector._calculate_fairness_metrics({}, {}, {})
        assert "source_balance_score" in result
        # Should handle missing keys gracefully

    def test_fairness_metrics_perfect_balance(self):
        """Test with perfectly balanced sources."""
        detector = BiasDetector()
        source = {"dominance_ratio": 0.33, "gini_coefficient": 0.0}
        temporal = {"recency_bias": 0.0}
        sec = {}
        result = detector._calculate_fairness_metrics(source, temporal, sec)
        assert result["source_balance_score"] > 50  # Should be high for balanced

    def test_fairness_metrics_high_dominance(self):
        """Test with high source dominance."""
        detector = BiasDetector()
        source = {"dominance_ratio": 0.9, "gini_coefficient": 0.7}
        temporal = {"recency_bias": 0.0}
        sec = {}
        result = detector._calculate_fairness_metrics(source, temporal, sec)
        assert result["source_balance_score"] < 50  # Should be low for imbalanced


@pytest.mark.unit
class TestGiniCoefficient:
    """Test Gini coefficient calculation."""

    def test_gini_perfectly_equal(self):
        """Test Gini coefficient with perfectly equal distribution."""
        detector = BiasDetector()
        values = np.array([10, 10, 10, 10])
        gini = detector._calculate_gini_coefficient(values)
        assert gini == pytest.approx(0.0, abs=0.01)

    def test_gini_perfectly_unequal(self):
        """Test Gini coefficient with maximum inequality."""
        detector = BiasDetector()
        values = np.array([100, 0, 0, 0])
        gini = detector._calculate_gini_coefficient(values)
        assert gini > 0.7  # Should be high

    def test_gini_empty_array(self):
        """Test Gini coefficient with empty array."""
        detector = BiasDetector()
        values = np.array([])
        gini = detector._calculate_gini_coefficient(values)
        assert gini == 0.0

    def test_gini_single_value(self):
        """Test Gini coefficient with single value."""
        detector = BiasDetector()
        values = np.array([10])
        gini = detector._calculate_gini_coefficient(values)
        assert gini == 0.0


@pytest.mark.unit
class TestRecencyBias:
    """Test recency bias calculation."""

    def test_recency_bias_all_recent(self):
        """Test with all recent dates."""
        detector = BiasDetector()
        dates = pd.to_datetime([
            datetime.now() - timedelta(days=1),
            datetime.now() - timedelta(days=2),
            datetime.now() - timedelta(days=3),
        ])
        bias = detector._calculate_recency_bias(dates)
        assert bias > 0.5  # Should indicate recent bias

    def test_recency_bias_all_old(self):
        """Test with all old dates."""
        detector = BiasDetector()
        dates = pd.to_datetime([
            datetime.now() - timedelta(days=365),
            datetime.now() - timedelta(days=400),
            datetime.now() - timedelta(days=500),
        ])
        bias = detector._calculate_recency_bias(dates)
        assert bias < 0.5  # Should indicate historical bias

    def test_recency_bias_single_date(self):
        """Test with single date."""
        detector = BiasDetector()
        dates = pd.to_datetime([datetime.now()])
        bias = detector._calculate_recency_bias(dates)
        assert 0 <= bias <= 1


@pytest.mark.unit
class TestMitigateBias:
    """Test bias mitigation functionality."""

    def test_mitigate_source_bias(self):
        """Test mitigation of source bias."""
        detector = BiasDetector()
        findings = [{"type": "source_bias", "severity": "high"}]
        data = {
            "news_articles": [
                {"source": "TechCrunch", "score": 1.0},
                {"source": "TechCrunch", "score": 1.0},
                {"source": "Other", "score": 1.0},
            ]
        }
        result = detector.mitigate_bias(findings, data)
        assert "mitigation_actions" in result
        assert len(result["mitigation_actions"]) > 0

    def test_mitigate_no_findings(self):
        """Test mitigation with no bias findings."""
        detector = BiasDetector()
        data = {"news_articles": [{"source": "Test"}]}
        result = detector.mitigate_bias([], data)
        assert result == data  # Should return unchanged

    def test_mitigate_multiple_bias_types(self):
        """Test mitigation of multiple bias types."""
        detector = BiasDetector()
        findings = [
            {"type": "source_bias", "severity": "high"},
            {"type": "temporal_bias", "severity": "medium"},
        ]
        data = {"news_articles": [{"source": "Test", "published_date": "2023-10-15"}]}
        result = detector.mitigate_bias(findings, data)
        assert len(result.get("mitigation_actions", [])) >= 2


@pytest.mark.unit
class TestReportSaving:
    """Test report saving functionality."""

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.makedirs")
    def test_save_report_creates_directory(self, mock_makedirs, mock_file):
        """Test that report saving creates output directory."""
        detector = BiasDetector()
        report = {"company_name": "Test Corp", "bias_detected": False}
        detector._save_report(report)
        mock_makedirs.assert_called_once()

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.makedirs")
    def test_save_report_writes_json(self, mock_makedirs, mock_file):
        """Test that report is saved as JSON."""
        detector = BiasDetector()
        report = {"company_name": "Test Corp", "bias_detected": False}
        detector._save_report(report)
        mock_file.assert_called_once()
        # Verify JSON was written
        handle = mock_file()
        assert handle.write.called


@pytest.mark.integration
class TestEndToEndBiasDetection:
    """Integration tests for complete bias detection flow."""

    def test_full_analysis_balanced_data(self):
        """Test complete analysis with balanced, high-quality data."""
        detector = BiasDetector()
        data = {
            "company_name": "Test Corp",
            "news_articles": [
                {"source": "Source A", "published_date": "2023-10-01", "word_count": 500},
                {"source": "Source B", "published_date": "2023-10-05", "word_count": 550},
                {"source": "Source C", "published_date": "2023-10-10", "word_count": 600},
            ],
            "sec_filings": {
                "10-K": {
                    "fiscal_year": "2023",
                    "sections": {"b": "1", "r": "2", "m": "3", "f": "4"},
                    "statistics": {"total_words": 50000}
                }
            }
        }
        with patch.object(detector, '_save_report'):
            result = detector.analyze_data(data)

        assert result["company_name"] == "Test Corp"
        assert result["bias_detected"] in [True, False]
        assert "fairness_metrics" in result
        assert "recommendations" in result

    def test_full_analysis_biased_data(self):
        """Test complete analysis with biased data."""
        detector = BiasDetector()
        data = {
            "company_name": "Biased Corp",
            "news_articles": [
                {"source": "SingleSource", "published_date": "2023-10-15", "word_count": 100},
                {"source": "SingleSource", "published_date": "2023-10-15", "word_count": 100},
                {"source": "SingleSource", "published_date": "2023-10-15", "word_count": 100},
            ],
            "sec_filings": {}
        }
        with patch.object(detector, '_save_report'):
            result = detector.analyze_data(data)

        # Should detect bias due to single source and single date
        assert "source_distribution" in result["analysis"]["news"]
        assert result["analysis"]["news"]["source_distribution"]["total_sources"] == 1
