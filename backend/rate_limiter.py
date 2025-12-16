"""
Token Bucket Rate Limiter for Recreation.gov API

Recreation.gov has a rate limit of 50 requests per minute.
This implements a thread-safe token bucket algorithm to ensure we stay well under that limit.
"""
import time
import threading
from typing import Optional


class TokenBucketRateLimiter:
    """
    Token bucket algorithm for rate limiting.
    
    - Tokens represent available requests
    - Tokens refill at a constant rate
    - Each request consumes one token
    - Blocks until a token is available
    """
    
    def __init__(self, rate: float = 40.0, capacity: int = 40):
        """
        Initialize the rate limiter.
        
        Args:
            rate: Tokens per minute (default 40 to stay safely under 50/min limit)
            capacity: Maximum tokens that can be stored (burst capacity)
        """
        self.rate = rate  # tokens per minute
        self.capacity = capacity  # max tokens
        self.tokens = capacity  # start full
        self.last_update = time.time()
        self.lock = threading.Lock()
        
        # Calculate token refill interval
        self.token_refill_interval = 60.0 / rate  # seconds per token
        
        print(f"Rate limiter initialized: {rate} requests/min, {self.token_refill_interval:.2f}s per request")
    
    def _refill_tokens(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        
        # Calculate new tokens to add
        new_tokens = elapsed / self.token_refill_interval
        
        if new_tokens > 0:
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_update = now
    
    def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        Acquire tokens, blocking until available.
        
        Args:
            tokens: Number of tokens to acquire (default 1)
            timeout: Maximum time to wait in seconds (None = wait forever)
        
        Returns:
            True if tokens acquired, False if timeout
        """
        start_time = time.time()
        
        while True:
            with self.lock:
                self._refill_tokens()
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False
            
            # Wait a bit before checking again
            # Sleep for a fraction of the refill interval
            time.sleep(self.token_refill_interval / 4)
    
    def acquire_with_wait(self, tokens: int = 1) -> float:
        """
        Acquire tokens and return the wait time.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            Time waited in seconds
        """
        start = time.time()
        self.acquire(tokens)
        wait_time = time.time() - start
        return wait_time
    
    def get_available_tokens(self) -> float:
        """Get current number of available tokens."""
        with self.lock:
            self._refill_tokens()
            return self.tokens
    
    def get_wait_time(self, tokens: int = 1) -> float:
        """
        Estimate wait time for acquiring tokens without actually acquiring them.
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Estimated wait time in seconds
        """
        with self.lock:
            self._refill_tokens()
            
            if self.tokens >= tokens:
                return 0.0
            
            tokens_needed = tokens - self.tokens
            return tokens_needed * self.token_refill_interval
    
    def reset(self):
        """Reset the rate limiter to full capacity."""
        with self.lock:
            self.tokens = self.capacity
            self.last_update = time.time()


# Global rate limiter instance
# Set to 35 requests per minute to be extra conservative
# This allows ~1.7 seconds between requests
rate_limiter = TokenBucketRateLimiter(rate=35.0, capacity=35)
