# src/utils/retry_handler.py
"""Retry logic with exponential backoff for handling transient failures"""

import time
import random
from typing import Callable, TypeVar, Any, Optional, Type, Tuple
from functools import wraps
import logging

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

from .logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


# Common retryable exceptions
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    Exception,  # Generic catch-all (be more specific in production)
)


class RetryHandler:
    """Handler for retry logic with exponential backoff"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """
        Initialize retry handler
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter to delays
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff: base_delay * (exponential_base ^ attempt)
        delay = self.base_delay * (self.exponential_base ** attempt)
        
        # Cap at max_delay
        delay = min(delay, self.max_delay)
        
        # Add jitter if enabled
        if self.jitter:
            delay = delay * (0.5 + random.random())  # Random between 50-150% of delay
        
        return delay
    
    def execute(
        self,
        func: Callable[..., T],
        *args,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
        **kwargs
    ) -> T:
        """
        Execute function with retry logic
        
        Args:
            func: Function to execute
            *args: Positional arguments for func
            retryable_exceptions: Tuple of exception types to retry on
            **kwargs: Keyword arguments for func
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries exhausted
        """
        retryable = retryable_exceptions or RETRYABLE_EXCEPTIONS
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    f"Attempt {attempt + 1}/{self.max_retries + 1} for {func.__name__}"
                )
                result = func(*args, **kwargs)
                
                if attempt > 0:
                    logger.info(
                        f"✅ {func.__name__} succeeded after {attempt + 1} attempts"
                    )
                
                return result
                
            except retryable as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = self.calculate_delay(attempt)
                    logger.warning(
                        f"⚠️  {func.__name__} failed (attempt {attempt + 1}): {str(e)}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"❌ {func.__name__} failed after {self.max_retries + 1} attempts"
                    )
                    raise
            
            except Exception as e:
                # Non-retryable exception
                logger.error(f"❌ {func.__name__} failed with non-retryable error: {str(e)}")
                raise
        
        # Should never reach here, but just in case
        if last_exception:
            raise last_exception


def retry_with_backoff(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
):
    """
    Decorator for retry with exponential backoff using tenacity
    
    Args:
        max_attempts: Maximum number of attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
        exponential_base: Base for exponential backoff
        retryable_exceptions: Exceptions to retry on
        
    Returns:
        Decorated function
    """
    retryable = retryable_exceptions or RETRYABLE_EXCEPTIONS
    
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(
            multiplier=min_wait,
            max=max_wait,
            exp_base=exponential_base
        ),
        retry=retry_if_exception_type(retryable),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG)
    )


# Convenience decorator with default settings
def retry_on_failure(func: Callable[..., T]) -> Callable[..., T]:
    """
    Simple decorator for retry with default settings
    
    Usage:
        @retry_on_failure
        def my_function():
            # code that might fail
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        handler = RetryHandler()
        return handler.execute(func, *args, **kwargs)
    
    return wrapper


