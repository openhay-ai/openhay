from __future__ import annotations

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.core.agents.chat.agent import chat_agent
from backend.core.agents.chat.deps import ChatDeps
from backend.settings import settings

router = APIRouter(prefix="/api/ai-tim-kiem", tags=["ai_tim_kiem"])


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    model: str


@router.post(
    "/chat",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Successful streaming response",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                        "example": (
                            'event: ai_message\ndata: {"chunk": {"content": "Hello!"}}\n\n'
                        ),
                    }
                }
            },
        },
        422: {"description": "Validation Error"},
    },
)
async def ai_tim_kiem_chat(payload: ChatRequest) -> StreamingResponse:
    logger = logging.getLogger(__name__)

    async def stream_generator():
        try:
            async with chat_agent.run_stream(payload.message, deps=ChatDeps()) as result:
                async for text_piece in result.stream_text(delta=True):
                    response = {
                        "chunk": {"content": text_piece},
                        "model": settings.model_name,
                    }
                    json_payload = json.dumps(response, ensure_ascii=False)
                    sse_message = f"event: ai_message\ndata: {json_payload}\n\n"
                    logger.debug("SSE message: %s", sse_message)
                    yield sse_message
        except Exception as exc:
            error_response = {
                "error": "Chat execution error",
                "error_type": type(exc).__name__,
                "details": str(exc),
            }
            json_payload = json.dumps(error_response, ensure_ascii=False)
            yield f"event: error\ndata: {json_payload}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream; charset=utf-8")


__all__ = ["router"]
