from __future__ import annotations

from typing import Awaitable, Callable

from backend.core.services.ratelimit import (
    RateLimiterRegistry,
    SlidingWindowRateLimiter,
    retry_predicate_for_provider,
    run_with_quota_and_retry,
    wait_llm_retry,
)
from backend.settings import settings


def _resolve_provider_and_model(model_name: str) -> tuple[str, str]:
    """Split provider and model by the first colon.

    Examples:
        "google-gla:gemini-2.5-flash" -> ("google-gla", "gemini-2.5-flash")
        "openai:gpt-4o" -> ("openai", "gpt-4o")
        "ollama:qwen3:8b" -> ("ollama", "qwen3:8b")
    """
    if ":" not in model_name:
        return model_name, "default"
    provider, model = model_name.split(":", 1)
    return provider, model


def _resolve_rpm(provider: str, model: str) -> int:
    """Return requests-per-minute policy per provider/model.

    Keep this simple and conservative; can be extended/configured later.
    """
    p = provider.lower()
    m = model.lower()

    if p.startswith("google"):
        if "gemini-2.5-flash" in m:
            return 10
        return 5
    if p.startswith("openai"):
        return 50
    if p.startswith("anthropic"):
        return 50
    if p.startswith("ollama"):
        return 30
    return 10


def _get_limiter_for_model(model_name: str) -> SlidingWindowRateLimiter:
    provider, model = _resolve_provider_and_model(model_name)
    rpm = _resolve_rpm(provider, model)
    key = f"rpm:{provider}:{model}:{rpm}"
    # 60 seconds window for RPM
    return RateLimiterRegistry.get(key, max_calls=rpm, per_seconds=60.0)


class LLMInvoker:
    """Orchestrates rate limiting and retries.

    Works for provider-agnostic model calls.
    """

    def __init__(self) -> None:
        # future: accept dependency overrides
        pass

    async def acquire(self) -> None:
        """Acquire the RPM limiter once (useful for pre-stream throttling)."""
        limiter = _get_limiter_for_model(settings.model_name)
        await limiter.acquire()

    async def run(
        self,
        operation_factory: Callable[[], Awaitable[object]],
        *,
        max_attempts: int = 3,
        retry: bool = True,
    ) -> object:
        """Run an async operation under RPM quota and provider-aware retries.

        The operation_factory must return a fresh awaitable per attempt.
        """
        limiter = _get_limiter_for_model(settings.model_name)

        if not retry or max_attempts <= 1:
            await limiter.acquire()
            return await operation_factory()

        provider, _ = _resolve_provider_and_model(settings.model_name)
        wait_fn = wait_llm_retry(provider)
        retry_fn = retry_predicate_for_provider(provider)
        return await run_with_quota_and_retry(
            limiter,
            operation_factory,
            max_attempts=max_attempts,
            wait_strategy=wait_fn,
            retry_predicate=retry_fn,
        )


# Singleton for convenience
llm_invoker = LLMInvoker()


__all__ = ["LLMInvoker", "llm_invoker"]
