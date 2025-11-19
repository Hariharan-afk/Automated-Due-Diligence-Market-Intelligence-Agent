# src/data_ingestion/base_fetcher.py
"""Base class for all data fetchers"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger
from src.utils.retry_handler import RetryHandler
from src.utils.rate_limiter import RateLimiter

logger = get_logger(__name__)


class BaseFetcher(ABC):
    """
    Abstract base class for data fetchers
    
    Provides common functionality:
    - Retry logic with exponential backoff
    - Rate limiting
    - Logging
    - Error handling
    """
    
    def __init__(
        self,
        rate_limit: Optional[float] = None,
        max_retries: int = 3,
        base_delay: float = 1.0
    ):
        """
        Initialize base fetcher
        
        Args:
            rate_limit: Maximum requests per second (None = no limit)
            max_retries: Maximum retry attempts
            base_delay: Initial delay for exponential backoff
        """
        self.retry_handler = RetryHandler(
            max_retries=max_retries,
            base_delay=base_delay
        )
        
        self.rate_limiter = RateLimiter(rate_limit) if rate_limit else None
        
        logger.info(f"{self.__class__.__name__} initialized")
    
    def _wait_for_rate_limit(self):
        """Wait if rate limit is active"""
        if self.rate_limiter:
            self.rate_limiter.wait_if_needed()
    
    @abstractmethod
    def fetch(self, *args, **kwargs) -> Any:
        """
        Fetch data from source
        
        Must be implemented by subclasses
        
        Returns:
            Fetched data in appropriate format
        """
        pass
    
    def fetch_with_retry(self, *args, **kwargs) -> Any:
        """
        Fetch data with retry logic
        
        Args:
            *args: Arguments to pass to fetch()
            **kwargs: Keyword arguments to pass to fetch()
            
        Returns:
            Fetched data
        """
        self._wait_for_rate_limit()
        
        return self.retry_handler.execute(
            self.fetch,
            *args,
            **kwargs
        )
    
    def validate_response(self, response: Any) -> bool:
        """
        Validate fetched response
        
        Can be overridden by subclasses
        
        Args:
            response: Response to validate
            
        Returns:
            True if valid, False otherwise
        """
        return response is not None
    
    def log_fetch_stats(self, source: str, count: int, duration: float):
        """
        Log fetching statistics
        
        Args:
            source: Data source name
            count: Number of items fetched
            duration: Time taken in seconds
        """
        logger.info(
            f"Fetched {count} items from {source} in {duration:.2f}s "
            f"({count/duration:.2f} items/sec)"
        )


