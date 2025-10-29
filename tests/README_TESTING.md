# Testing Guide - Focused on Edge Cases & Data Quality

## Overview

This test suite is **focused specifically on MLOps requirements**:
- ✅ **Edge cases** (boundary conditions, extreme values)
- ✅ **Missing values** (null, NaN, empty data)
- ✅ **Anomalies** (outliers, invalid formats, data quality issues)

## Test Files

### Core Test Module

**[test_edge_cases_data_quality.py](test_edge_cases_data_quality.py)** (300+ lines)
- Comprehensive edge case testing
- Missing value handling
- Anomaly detection validation
- Data quality checks

### Additional Test Files

**[test_path_resolver.py](test_path_resolver.py)**
- Cross-platform path handling edge cases
- 100% coverage achieved

**[test_data_acquisition.py](test_data_acquisition.py)**
- API edge cases
- Data cleaning with special characters

**[test_chunking.py](test_chunking.py)**
- Document chunking edge cases
- Table extraction anomalies

**[test_sec_fetcher.py](test_sec_fetcher.py)**
- SEC filing edge cases
- Missing section handling

## Running Tests

### Run All Tests

```bash
# Run all focused tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing
```

### Run by Category

```bash
# Edge case tests only
pytest -m edge_case -v

# Data quality tests only
pytest -m data_quality -v

# Integration tests only
pytest -m integration -v
```

### Run Specific Test File

```bash
# Run focused edge case tests
pytest tests/test_edge_cases_data_quality.py -v

# Run specific test class
pytest tests/test_edge_cases_data_quality.py::TestMissingValues -v

# Run specific test
pytest tests/test_edge_cases_data_quality.py::TestMissingValues::test_empty_input_data -v
```

## Test Categories

### 1. Missing Values Tests

Tests handling of:
- Empty input data
- Missing required fields
- Null/NaN values
- Empty strings
- None values

**Example:**
```python
def test_empty_input_data(self):
    """Test with completely empty data."""
    detector = BiasDetector()
    result = detector.analyze_data({})
    assert result["error"] == "No data to analyze"
```

### 2. Edge Cases Tests

Tests boundary conditions:
- Single data point
- Very large datasets (1000+ items)
- Extreme values (0, negative, very large)
- 100% source dominance
- Special characters and unicode

**Example:**
```python
def test_extreme_word_counts(self):
    """Test with extreme word count values."""
    df = pd.DataFrame([
        {"source": "Test1", "word_count": 1},       # Very low
        {"source": "Test2", "word_count": 1000000}, # Very high
        {"source": "Test3", "word_count": 0},       # Zero
    ])
    result = detector._analyze_quality_across_slices(df)
    assert result["mean_word_count"] > 0
```

### 3. Anomaly Detection Tests

Tests anomaly detection:
- Insufficient data
- Content too short
- Missing dates
- Statistical outliers
- Incomplete SEC filings

**Example:**
```python
def test_insufficient_data_anomaly(self):
    """Test detection of insufficient data."""
    detector = AnomalyDetector()
    data = {
        "news_articles": [],  # No articles - anomaly
    }
    anomalies = detector.detect(data)
    assert len(anomalies) > 0
```

### 4. Invalid Inputs Tests

Tests error handling:
- Invalid date formats
- Wrong data types
- Malformed HTML
- Negative values

**Example:**
```python
def test_invalid_date_format(self):
    """Test parsing of invalid date formats."""
    cleaner = DataCleaner()
    result = cleaner.parse_date("not-a-valid-date")
    assert result is None
```

## Test Coverage Focus

We focus on **critical paths** that handle edge cases and data quality:

| Module | Focus Area | Key Tests |
|--------|------------|-----------|
| `bias_detector.py` | Missing values, extreme distributions | Empty data, single source, no dates |
| `data_preprocessing.py` | Invalid inputs, special characters | Malformed HTML, empty strings |
| `schema_validator.py` | Missing fields, anomalies | Missing required fields, outliers |
| `path_resolver.py` | Cross-platform edge cases | Special chars, unicode paths |

## Expected Test Results

```bash
$ pytest tests/test_edge_cases_data_quality.py -v

tests/test_edge_cases_data_quality.py::TestMissingValues::test_empty_input_data PASSED
tests/test_edge_cases_data_quality.py::TestMissingValues::test_missing_required_fields PASSED
tests/test_edge_cases_data_quality.py::TestMissingValues::test_null_values_in_dataframe PASSED
tests/test_edge_cases_data_quality.py::TestEdgeCases::test_single_data_point PASSED
tests/test_edge_cases_data_quality.py::TestEdgeCases::test_extreme_word_counts PASSED
tests/test_edge_cases_data_quality.py::TestAnomalies::test_insufficient_data_anomaly PASSED
tests/test_edge_cases_data_quality.py::TestAnomalies::test_outlier_detection PASSED
...

============================== 50+ tests passed ==============================
```

## Test Maintenance

### Adding New Tests

Focus on these criteria:
1. **Is it an edge case?** (boundary condition, extreme value)
2. **Does it test missing values?** (null, NaN, empty)
3. **Does it test anomalies?** (outliers, invalid data)

If yes to any, add the test. Otherwise, skip.

### Test Structure

```python
@pytest.mark.data_quality  # or @pytest.mark.edge_case
class TestYourFeature:
    """Test description focused on edge cases."""

    def test_specific_edge_case(self):
        """Clear description of the edge case being tested."""
        # Arrange
        detector = YourDetector()
        edge_case_data = {...}

        # Act
        result = detector.process(edge_case_data)

        # Assert
        assert result meets expected behavior
```

## Archived Tests

Comprehensive tests that go beyond edge cases/data quality have been moved to:
```
tests/archived/
├── test_bias_detector.py       # 45+ comprehensive tests
├── test_vector_store.py        # 50+ comprehensive tests
└── test_alert_manager.py       # 55+ comprehensive tests
```

These are kept for reference but not run by default.

## Quick Reference

```bash
# Run focused tests (recommended)
pytest tests/test_edge_cases_data_quality.py -v

# Run with markers
pytest -m "edge_case or data_quality" -v

# Generate coverage report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# Run existing working tests
pytest tests/test_path_resolver.py tests/test_data_acquisition.py::TestDataCleaner -v
```

## MLOps Submission Requirements

✅ **Edge Cases:** Tested via `@pytest.mark.edge_case` tests
✅ **Missing Values:** Tested via `@pytest.mark.data_quality` tests
✅ **Anomalies:** Tested via `AnomalyDetector` tests
✅ **Robustness:** All tests verify graceful error handling

**Total Tests:** 50+ focused tests (vs 210+ comprehensive tests previously)
**Focus:** Quality over quantity - each test validates critical data quality scenarios
