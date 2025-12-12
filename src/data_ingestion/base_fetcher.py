# src/data_ingestion/base_fetcher.py
"""Base fetcher class with rate limiting and retry logic"""

import time
from typing import Callable, Any
from functools import wraps

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class BaseFetcher:
    """
    Base class for all data fetchers
    
    Features:
    - Rate limiting
    - Retry logic with exponential backoff
    - Error handling
    """
    
    def __init__(self, rate_limit: float = 10.0, max_retries: int = 3):
        """
        Initialize base fetcher
        
        Args:
            rate_limit: Max requests per second
            max_retries: Max retry attempts
        """
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.min_interval = 1.0 / rate_limit  # Minimum time between requests
        self.last_request_time = 0
    
    def _rate_limit_wait(self):
        """Wait to respect rate limit"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def fetch_with_retry(self, *args, **kwargs) -> Any:
        """
        Fetch data with retry logic
        
        Calls self.fetch() with retries
        """
        for attempt in range(self.max_retries):
            try:
                self._rate_limit_wait()
                result = self.fetch(*args, **kwargs)
                return result
            
            except Exception as e:
                logger.warning(f"Fetch attempt {attempt + 1}/{self.max_retries} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {self.max_retries} attempts failed")
                    raise
    
    def fetch(self, *args, **kwargs) -> Any:
        """
        Main fetch method (to be overridden by subclasses)
        """
        raise NotImplementedError("Subclasses must implement fetch()")