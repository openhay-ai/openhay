from __future__ import annotations

import asyncio
from collections import deque
import re
import random
from time import monotonic
from typing import Callable, Deque, Dict

from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    RetryCallState,
)
from google.genai.errors import ClientError


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


def wait_gemini_retry(
    fallback_strategy: Callable[[RetryCallState], float] | None = None,
    max_wait: float = 300,
) -> Callable[[RetryCallState], float]:
    """Create a wait strategy that parses Gemini's retryDelay from error messages."""
    if fallback_strategy is None:
        fallback_strategy = wait_exponential(multiplier=1, max=60)

    def wait_func(state: RetryCallState) -> float:
        exc = state.outcome.exception() if state.outcome else None
        if not (isinstance(exc, ClientError) and "RESOURCE_EXHAUSTED" in str(exc)):
            return fallback_strategy(state)

        message = str(exc)
        m = re.search(r"'retryDelay':\s*'(?P<secs>\d+)s'", message)
        delay_seconds = float(m.group("secs")) if m else 60.0
        backoff = delay_seconds * (1.2 ** (state.attempt_number - 1)) + random.uniform(0, 0.5)
        return min(backoff, max_wait)

    return wait_func


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

    controller = AsyncRetrying(
        retry=retry_if_exception(
            lambda exc: isinstance(exc, ClientError) and "RESOURCE_EXHAUSTED" in str(exc)
        ),
        wait=wait_gemini_retry(),
        stop=stop_after_attempt(max_attempts),
        reraise=True,
    )

    async for attempt in controller:
        with attempt:
            await limiter.acquire()
            return await operation()

    raise RuntimeError("The retry controller did not make any attempts")


__all__ = [
    "SlidingWindowRateLimiter",
    "RateLimiterRegistry",
    "gemini_flash_limiter",
    "gemini_pro_limiter",
    "run_with_quota_and_retry",
]
