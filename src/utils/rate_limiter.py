# src/utils/rate_limiter.py
"""Rate limiting for API calls"""

import time
from threading import Lock
from typing import Optional
from collections import deque
from datetime import datetime, timedelta

from .logging_config import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Thread-safe rate limiter using token bucket algorithm
    """
    
    def __init__(
        self,
        requests_per_second: float,
        burst_size: Optional[int] = None
    ):
        """
        Initialize rate limiter
        
        Args:
            requests_per_second: Maximum requests per second
            burst_size: Maximum burst size (default: requests_per_second)
        """
        self.rate = requests_per_second
        self.burst_size = burst_size or int(requests_per_second)
        self.tokens = self.burst_size
        self.last_update = time.time()
        self.lock = Lock()
        
        logger.debug(
            f"RateLimiter initialized: {requests_per_second} req/s, "
            f"burst={self.burst_size}"
        )
    
    def _add_tokens(self):
        """Add tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_update
        
        # Add tokens based on elapsed time
        new_tokens = elapsed * self.rate
        self.tokens = min(self.burst_size, self.tokens + new_tokens)
        self.last_update = now
    
    def wait_if_needed(self):
        """
        Block until rate limit allows request
        
        This method will block if rate limit is exceeded
        """
        with self.lock:
            self._add_tokens()
            
            if self.tokens >= 1:
                # Token available, consume it
                self.tokens -= 1
                return
            
            # Need to wait for token
            wait_time = (1 - self.tokens) / self.rate
            logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
            time.sleep(wait_time)
            
            # After waiting, consume token
            self._add_tokens()
            self.tokens -= 1
    
    def try_acquire(self) -> bool:
        """
        Try to acquire a token without blocking
        
        Returns:
            True if token acquired, False if rate limited
        """
        with self.lock:
            self._add_tokens()
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            
            return False


class SlidingWindowRateLimiter:
    """
    Rate limiter using sliding window algorithm
    
    More accurate than token bucket for bursty traffic
    """
    
    def __init__(
        self,
        max_requests: int,
        window_seconds: float
    ):
        """
        Initialize sliding window rate limiter
        
        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests = deque()
        self.lock = Lock()
        
        logger.debug(
            f"SlidingWindowRateLimiter initialized: "
            f"{max_requests} requests per {window_seconds}s"
        )
    
    def _cleanup_old_requests(self):
        """Remove requests outside the time window"""
        now = datetime.now()
        cutoff = now - self.window
        
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()
    
    def wait_if_needed(self):
        """Block until rate limit allows request"""
        with self.lock:
            self._cleanup_old_requests()
            
            if len(self.requests) < self.max_requests:
                # Under limit, record request
                self.requests.append(datetime.now())
                return
            
            # Need to wait
            oldest_request = self.requests[0]
            wait_until = oldest_request + self.window
            wait_time = (wait_until - datetime.now()).total_seconds()
            
            if wait_time > 0:
                logger.debug(
                    f"Rate limit reached, waiting {wait_time:.2f}s "
                    f"({len(self.requests)}/{self.max_requests} requests)"
                )
                time.sleep(wait_time)
            
            # After waiting, record request
            self._cleanup_old_requests()
            self.requests.append(datetime.now())
    
    def try_acquire(self) -> bool:
        """Try to acquire without blocking"""
        with self.lock:
            self._cleanup_old_requests()
            
            if len(self.requests) < self.max_requests:
                self.requests.append(datetime.now())
                return True
            
            return False


class MultiRateLimiter:
    """
    Combine multiple rate limiters (e.g., per-second and per-minute)
    """
    
    def __init__(self, *limiters):
        """
        Initialize with multiple rate limiters
        
        Args:
            *limiters: RateLimiter instances
        """
        self.limiters = limiters
    
    def wait_if_needed(self):
        """Wait for all rate limiters"""
        for limiter in self.limiters:
            limiter.wait_if_needed()
    
    def try_acquire(self) -> bool:
        """Try to acquire from all limiters"""
        return all(limiter.try_acquire() for limiter in self.limiters)


