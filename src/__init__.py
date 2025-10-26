"""
Company Research Data Pipeline - Source Package
MLOps Project

This package contains all core modules for the data pipeline:
- data_acquisition: Fetch data from Wikipedia and News APIs
- data_preprocessing: Clean and normalize data
- schema_validator: Validate data structure and quality
- bias_detector: Detect and analyze bias
- db_manager: Database operations
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

# Import main classes for easier access
from .data_acquisition import (
    CompanyTickerMatcher,
    WikipediaDataFetcher,
    NewsAPIFetcher,
    DataAcquisitionPipeline
)

from .data_preprocessing import (
    DataCleaner,
    WikipediaPreprocessor,
    NewsPreprocessor,
    DataPreprocessingPipeline
)

from .schema_validator import (
    SchemaValidator,
    AnomalyDetector,
    DataQualityReport
)

from .bias_detector import BiasDetector

from .db_manager import init_db, insert_company, insert_article, get_company, get_articles, export_to_csv

__all__ = [
    # Data Acquisition
    'CompanyTickerMatcher',
    'WikipediaDataFetcher',
    'NewsAPIFetcher',
    'DataAcquisitionPipeline',
    
    # Preprocessing
    'DataCleaner',
    'WikipediaPreprocessor',
    'NewsPreprocessor',
    'DataPreprocessingPipeline',
    
    # Validation
    'SchemaValidator',
    'AnomalyDetector',
    'DataQualityReport',
    
    # Bias Detection
    'BiasDetector',
    
    # Database
    'init_db',
    'insert_company',
    'insert_article',
    'get_company',
    'get_articles',
    'export_to_csv',
]