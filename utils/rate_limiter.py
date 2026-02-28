"""
Rate Limiting and Retry Decorators
"""

import time
import random
import logging
from functools import wraps
from typing import Callable, Optional, Type, Union, Tuple

logger = logging.getLogger(__name__)

class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted"""
    pass

def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    jitter: bool = True,
    logger: Optional[logging.Logger] = None
) -> Callable:
    """
    Retry decorator with exponential backoff
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Exception types to catch and retry
        jitter: Add random jitter to delay to avoid thundering herd
        logger: Logger to use for logging retries
    
    Returns:
        Decorated function
    
    Example:
        @retry(max_attempts=5, delay=2, backoff=2)
        def flaky_function():
            # This will retry up to 5 times with delays: 2, 4, 8, 16, 32 seconds
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            _delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        # Last attempt failed
                        msg = f"All {max_attempts} attempts failed for {func.__name__}"
                        if logger:
                            logger.error(msg)
                        else:
                            print(f"❌ {msg}")
                        raise RetryExhaustedError(msg) from e
                    
                    # Calculate next delay with optional jitter
                    sleep_time = _delay
                    if jitter:
                        # Add ±25% jitter
                        jitter_amount = sleep_time * 0.25
                        sleep_time += random.uniform(-jitter_amount, jitter_amount)
                        sleep_time = max(0.1, sleep_time)  # Ensure positive
                    
                    msg = (f"Attempt {attempt + 1}/{max_attempts} failed for "
                          f"{func.__name__}: {e}. Retrying in {sleep_time:.2f}s")
                    if logger:
                        logger.warning(msg)
                    else:
                        print(f"⚠️ {msg}")
                    
                    time.sleep(sleep_time)
                    _delay *= backoff
            
            # Should never reach here
            raise RetryExhaustedError(f"Unexpected retry exhaustion in {func.__name__}")
        
        return wrapper
    return decorator

class RateLimiter:
    """
    Rate limiter for API calls
    Ensures we don't exceed calls per minute limits
    """
    
    def __init__(self, calls_per_minute: int = 30, name: str = "default"):
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute
        self.last_call = 0
        self.name = name
        self.call_count = 0
        self.reset_time = time.time()
    
    def wait_if_needed(self) -> float:
        """
        Wait if necessary to stay under rate limit
        Returns the time waited in seconds
        """
        now = time.time()
        
        # Reset counter every minute
        if now - self.reset_time > 60:
            self.call_count = 0
            self.reset_time = now
        
        # Calculate wait time
        time_since_last = now - self.last_call
        wait_time = 0
        
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            time.sleep(wait_time)
        
        self.last_call = time.time()
        self.call_count += 1
        
        return wait_time
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator version"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            self.wait_if_needed()
            return func(*args, **kwargs)
        return wrapper
    
    def __enter__(self):
        """Context manager entry"""
        self.wait_if_needed()
        return self
    
    def __exit__(self, *args):
        """Context manager exit"""
        pass

class CircuitBreaker:
    """
    Circuit breaker pattern to prevent repeated calls to failing services
    """
    
    STATES = ['CLOSED', 'OPEN', 'HALF_OPEN']
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.state = 'CLOSED'
        self.failure_count = 0
        self.last_failure_time = 0
        self.logger = logging.getLogger(f'CircuitBreaker.{name}')
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator version"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper
    
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        
        # Check if circuit is open
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
                self.logger.info(f"Circuit {self.name} half-open, allowing test request")
            else:
                self.logger.warning(f"Circuit {self.name} is OPEN, failing fast")
                raise Exception(f"Circuit breaker for {self.name} is OPEN")
        
        try:
            result = func(*args, **kwargs)
            
            # Success - reset if half-open
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
                self.logger.info(f"Circuit {self.name} closed (test successful)")
            
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == 'HALF_OPEN' or self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
                self.logger.error(f"Circuit {self.name} opened after {self.failure_count} failures")
            
            raise

# Convenience decorator for common use cases
def with_retry(max_attempts: int = 3):
    """Simple retry decorator with default settings"""
    return retry(
        max_attempts=max_attempts,
        delay=2,
        backoff=2,
        exceptions=(Exception,),
        jitter=True
    )