from __future__ import annotations

import asyncio
from collections import deque
import re
import random
from time import monotonic
from typing import Deque, Dict


class SlidingWindowRateLimiter:
    """Async sliding-window rate limiter.

    Ensures no more than `max_calls` occur within any `per_seconds` window.
    Safe for concurrent usage within a single process.
    """

    def __init__(self, max_calls: int, per_seconds: float) -> None:
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self._lock = asyncio.Lock()
        self._events: Deque[float] = deque()

    async def acquire(self) -> None:
        """Wait until an event is allowed and record it."""
        while True:
            async with self._lock:
                now = monotonic()
                # Drop stale events
                boundary = now - self.per_seconds
                while self._events and self._events[0] <= boundary:
                    self._events.popleft()

                if len(self._events) < self.max_calls:
                    self._events.append(now)
                    return

                # Need to wait until the oldest event falls out of the window
                wait_time = (self._events[0] + self.per_seconds) - now

            # Sleep outside the lock
            # Add a small cushion to avoid thrashing near the boundary
            await asyncio.sleep(max(wait_time, 0.01))


class RateLimiterRegistry:
    """Registry of named process-wide limiters."""

    _instances: Dict[str, SlidingWindowRateLimiter] = {}

    @classmethod
    def get(cls, key: str, *, max_calls: int, per_seconds: float) -> SlidingWindowRateLimiter:
        limiter = cls._instances.get(key)
        if limiter is None:
            limiter = SlidingWindowRateLimiter(max_calls=max_calls, per_seconds=per_seconds)
            cls._instances[key] = limiter
        return limiter


def gemini_flash_limiter() -> SlidingWindowRateLimiter:
    """Gemini Flash: 10 requests per minute."""
    return RateLimiterRegistry.get("gemini-flash-rpm", max_calls=10, per_seconds=60.0)


def gemini_pro_limiter() -> SlidingWindowRateLimiter:
    """Gemini Pro: 5 requests per minute."""
    return RateLimiterRegistry.get("gemini-pro-rpm", max_calls=5, per_seconds=60.0)


async def run_with_quota_and_retry(
    limiter: SlidingWindowRateLimiter,
    operation,
    *,
    max_attempts: int = 3,
) -> object:
    """Run an async operation under a limiter with robust retry on quota errors.

    - Acquires the provided limiter before each attempt
    - Retries on Google Gemini 429 RESOURCE_EXHAUSTED using server-suggested retryDelay when available
    - Uses a small jitter to avoid thundering herd
    """

    attempt = 0
    while True:
        attempt += 1
        await limiter.acquire()
        try:
            return await operation()
        except Exception as exc:  # Lazy import and targeted handling
            # Only handle Google Gemini quota errors; otherwise re-raise
            try:
                from google.genai.errors import ClientError  # type: ignore
            except Exception:  # If library shape changes or not present, re-raise
                raise

            if isinstance(exc, ClientError) and "RESOURCE_EXHAUSTED" in str(exc):
                # Try to extract server-provided retry delay (e.g., "'retryDelay': '51s'")
                message = str(exc)
                m = re.search(r"'retryDelay':\s*'(?P<secs>\d+)s'", message)
                delay_seconds = float(m.group("secs")) if m else 60.0
                # Add small jitter (0-0.5s) and exponential factor per attempt
                backoff = delay_seconds * (1.2 ** (attempt - 1)) + random.random() * 0.5

                if attempt >= max_attempts:
                    raise

                await asyncio.sleep(backoff)
                continue

            # Non-quota or unknown error: propagate
            raise


__all__ = [
    "SlidingWindowRateLimiter",
    "RateLimiterRegistry",
    "gemini_flash_limiter",
    "gemini_pro_limiter",
    "run_with_quota_and_retry",
]
