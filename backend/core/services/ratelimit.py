from __future__ import annotations

import asyncio
from collections import deque
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


__all__ = [
    "SlidingWindowRateLimiter",
    "RateLimiterRegistry",
    "gemini_flash_limiter",
    "gemini_pro_limiter",
]
