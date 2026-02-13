"""
Rate limiter for Gemini API to ensure compliance with quota limits.
"""
import time
from datetime import datetime, timedelta
from typing import Optional


class GeminiRateLimiter:
    """
    Ensures compliance with Gemini API rate limits.
    
    Default limits:
    - 5 requests per minute (RPM)
    - 20 requests per day (RPD)
    
    Usage:
        limiter = GeminiRateLimiter()
        limiter.wait_if_needed()  # Blocks if necessary
        # Make API call
    """
    
    def __init__(self, rpm: int = 5, rpd: int = 20):
        """
        Initialize rate limiter.
        
        Args:
            rpm: Requests per minute limit
            rpd: Requests per day limit
        """
        self.rpm = rpm
        self.rpd = rpd
        self.min_interval = 60 / rpm  # Seconds between calls
        self.last_call_time: Optional[float] = None
        self.daily_calls = 0
        self.last_reset_date = datetime.now().date()
        self.call_history = []  # Track recent calls for debugging
    
    def wait_if_needed(self) -> dict:
        """
        Block execution if necessary to respect rate limits.
        
        Returns:
            dict with status information
            
        Raises:
            Exception if daily limit exceeded
        """
        # Reset daily counter if new day
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.daily_calls = 0
            self.last_reset_date = today
            self.call_history.clear()
        
        # Check daily limit
        if self.daily_calls >= self.rpd:
            raise Exception(
                f"Daily limit of {self.rpd} requests exceeded. "
                f"Reset at midnight. Current count: {self.daily_calls}"
            )
        
        # Check per-minute limit and wait if needed
        wait_time = 0
        if self.last_call_time:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                print(f"⏳ Rate limit: waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
        
        # Record this call
        self.last_call_time = time.time()
        self.daily_calls += 1
        self.call_history.append({
            "timestamp": datetime.now(),
            "call_number": self.daily_calls,
            "waited": wait_time
        })
        
        return {
            "call_number": self.daily_calls,
            "daily_limit": self.rpd,
            "waited_seconds": wait_time,
            "remaining_today": self.rpd - self.daily_calls
        }
    
    def get_status(self) -> dict:
        """Get current rate limiter status."""
        return {
            "daily_calls": self.daily_calls,
            "daily_limit": self.rpd,
            "remaining_today": self.rpd - self.daily_calls,
            "last_call": self.last_call_time,
            "min_interval_seconds": self.min_interval
        }
