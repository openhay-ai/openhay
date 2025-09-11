from __future__ import annotations

import asyncio
import random
import re
from collections import deque
from datetime import datetime, timezone
from time import monotonic
from typing import Callable, Deque, Dict

from google.genai.errors import ClientError
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)


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
    def get(
        cls,
        key: str,
        *,
        max_calls: int,
        per_seconds: float,
    ) -> SlidingWindowRateLimiter:
        limiter = cls._instances.get(key)
        if limiter is None:
            limiter = SlidingWindowRateLimiter(
                max_calls=max_calls,
                per_seconds=per_seconds,
            )
            cls._instances[key] = limiter
        return limiter


def _get_http_status(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(exc, "response", None)
    if response is None:
        return None
    status = getattr(response, "status", None)
    if isinstance(status, int):
        return status
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def _get_headers(exc: Exception) -> dict[str, str] | None:
    response = getattr(exc, "response", None)
    hdrs = getattr(response, "headers", None) if response is not None else None
    if hdrs is None:
        return None
    try:
        # normalize keys to lowercase strings
        return {str(k).lower(): str(v) for k, v in hdrs.items()}
    except Exception:
        return None


def _parse_retry_after(value: str) -> float | None:
    # Prefer simple numeric seconds
    try:
        secs = float(value.strip())
        if secs >= 0:
            return secs
    except Exception:
        pass
    # Try HTTP-date (best-effort)
    try:
        dt = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %Z")
        # If timezone missing, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        delta = (dt - now).total_seconds()
        if delta > 0:
            return delta
    except Exception:
        return None
    return None


def _parse_reset_header(value: str) -> float | None:
    """Parse OpenAI/Anthropic reset headers.

    Accept numeric seconds or future epoch seconds; ignore invalid formats.
    """
    try:
        num = float(value.strip())
        if num <= 0:
            return None
        # If it's a large value (looks like epoch), convert to delta
        if num > 10_000_000:  # ~1970-04-26 in seconds
            now = datetime.now(tz=timezone.utc).timestamp()
            if num > now:
                return max(num - now, 0.0)
        return num
    except Exception:
        return None


def wait_llm_retry(
    provider: str,
    *,
    fallback_strategy: Callable[[RetryCallState], float] | None = None,
    max_wait: float = 300,
) -> Callable[[RetryCallState], float]:
    """Provider-aware wait strategy using server hints when available.

    Providers:
      - "google": parse retryDelay seconds from Gemini errors
      - "openai": use Retry-After or x-ratelimit-reset-requests/tokens
      - "anthropic": use retry-after when present; treat 429/529 similarly
    """
    if fallback_strategy is None:
        fallback_strategy = wait_exponential(multiplier=1, max=60)

    prov = (provider or "").lower()

    def wait_func(state: RetryCallState) -> float:
        exc = state.outcome.exception() if state.outcome else None
        if exc is None:
            return fallback_strategy(state)

        # Google Gemini: parse retryDelay from error message
        if prov.startswith("google"):
            if not (isinstance(exc, ClientError) and "RESOURCE_EXHAUSTED" in str(exc)):
                return fallback_strategy(state)
            message = str(exc)
            m = re.search(r"'retryDelay':\s*'(?P<secs>\d+)s'", message)
            delay_seconds = float(m.group("secs")) if m else 60.0
            backoff = delay_seconds * (1.2 ** (state.attempt_number - 1)) + random.uniform(0, 0.5)
            return min(backoff, max_wait)

        # OpenAI & Anthropic: look for headers
        headers = _get_headers(exc) or {}
        retry_after = headers.get("retry-after")
        if retry_after:
            parsed = _parse_retry_after(retry_after)
            if parsed is not None:
                backoff = parsed * (1.2 ** (state.attempt_number - 1))
                backoff += random.uniform(0, 0.5)
                return min(backoff, max_wait)

        # OpenAI reset headers (best-effort)
        if prov.startswith("openai"):
            reset_candidates = [
                headers.get("x-ratelimit-reset-requests"),
                headers.get("x-ratelimit-reset-tokens"),
            ]
            for val in reset_candidates:
                if not val:
                    continue
                parsed = _parse_reset_header(val)
                if parsed is not None:
                    backoff = parsed * (1.2 ** (state.attempt_number - 1))
                    backoff += random.uniform(0, 0.5)
                    return min(backoff, max_wait)

        # Default fallback
        return fallback_strategy(state)

    return wait_func


def retry_predicate_for_provider(provider: str) -> Callable[[BaseException], bool]:
    prov = (provider or "").lower()

    def _get_status(exc: BaseException) -> int | None:
        try:
            return _get_http_status(exc)  # type: ignore[arg-type]
        except Exception:
            return None

    if prov.startswith("google"):
        return lambda exc: (isinstance(exc, ClientError) and "RESOURCE_EXHAUSTED" in str(exc))

    if prov.startswith("anthropic"):
        try:
            from anthropic._exceptions import (
                OverloadedError as AnthropicOverloadedError,
            )
            from anthropic._exceptions import (
                RateLimitError as AnthropicRateLimitError,  # type: ignore
            )

            return lambda exc: (
                isinstance(exc, (AnthropicRateLimitError, AnthropicOverloadedError))
                or (_get_status(exc) in (429, 529))
            )
        except Exception:
            return lambda exc: (_get_status(exc) in (429, 529))

    if prov.startswith("openai"):
        try:
            from openai._exceptions import RateLimitError as OpenAIRateLimitError  # type: ignore

            return lambda exc: (isinstance(exc, OpenAIRateLimitError) or (_get_status(exc) == 429))
        except Exception:
            return lambda exc: (_get_status(exc) == 429)

    # Default: retry only on 429
    return lambda exc: (_get_status(exc) == 429)


async def run_with_quota_and_retry(
    limiter: SlidingWindowRateLimiter,
    operation,
    *,
    max_attempts: int = 3,
    wait_strategy: Callable[[RetryCallState], float] | None = None,
    retry_predicate: Callable[[BaseException], bool] | None = None,
) -> object:
    """Run an async operation under a limiter with retries on quota errors.

    - Acquire the limiter before each attempt.
    - Retry on Google Gemini 429 RESOURCE_EXHAUSTED using server-suggested
      retryDelay when available.
    - Use a small jitter to avoid thundering herd.
    """
    retry_fn = retry_predicate or (
        lambda exc: (isinstance(exc, ClientError) and "RESOURCE_EXHAUSTED" in str(exc))
    )
    wait_fn = wait_strategy or wait_exponential(multiplier=1, max=60)

    controller = AsyncRetrying(
        retry=retry_if_exception(retry_fn),
        wait=wait_fn,
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
    "run_with_quota_and_retry",
    "wait_llm_retry",
    "retry_predicate_for_provider",
]
