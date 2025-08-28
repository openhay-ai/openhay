from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Awaitable, Callable, Optional

from backend.core.services.llm_invoker import llm_invoker
from backend.settings import settings


def format_sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


async def stream_agent_text(
    agent: Any,
    user_prompt: Any,
    *,
    deps: Any,
    message_history: Optional[list[Any]] = None,
    on_complete: Optional[Callable[[Any], Awaitable[list[str]]]] = None,
) -> AsyncGenerator[str, None]:
    """Stream assistant text as SSE messages and optionally run completion hook.

    Parameters
    - agent: pydantic-ai Agent-like object exposing run_stream(...)
    - user_prompt: string | list[BinaryContent | str]
    - deps: dependency object passed to the agent
    - message_history: prior ModelMessage list
    - on_complete: async callback receiving the run result; returns extra SSE events
    """

    # Rate-limit guard per provider
    await llm_invoker.acquire()

    async with agent.run_stream(
        user_prompt,
        deps=deps,
        message_history=message_history,
    ) as result:
        async for text_piece in result.stream_text(delta=True):
            yield format_sse(
                "ai_message",
                {
                    "chunk": {"content": text_piece},
                    "model": settings.model.model_name,
                },
            )

        if on_complete is not None:
            try:
                extra_events = await on_complete(result)
                for evt in extra_events:
                    yield evt
            except Exception:
                # Swallow completion hook errors to avoid breaking the stream termination
                # Logging is left to the caller where session context is available
                pass


__all__ = ["format_sse", "stream_agent_text"]
