from __future__ import annotations

import json

from backend.api.routers.models.requests import (
    TranslateFileRequest,
    TranslateURLRequest,
)
from backend.core.agents.translate.agent import translate_agent
from backend.core.agents.translate.deps import TranslateDeps
from backend.core.auth import CurrentUser
from backend.core.services.streaming import format_sse, stream_agent_text
from backend.core.services.translate import TranslateService
from backend.db import AsyncSessionLocal
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic_ai.messages import ModelMessagesTypeAdapter

router = APIRouter(prefix="/api/translate", tags=["translate"])


@router.post(
    "/url",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Successful streaming response",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                        "example": (
                            'event: ai_message\ndata: {"chunk": {"content": "Xin chào"}}\n\n'
                        ),
                    }
                }
            },
        },
        422: {"description": "Validation Error"},
    },
)
async def translate_url(
    payload: TranslateURLRequest, current_user: CurrentUser
) -> StreamingResponse:
    async def stream_generator():
        try:
            async with AsyncSessionLocal() as session:
                svc = TranslateService(session)

                # Resolve existing conversation or create a new one
                conversation = None
                created_new_conversation = False
                if payload.conversation_id is not None:
                    conversation = await svc.get_conversation_by_id(payload.conversation_id)
                if conversation is None:
                    conversation = await svc.create_conversation_with_preset()
                    created_new_conversation = True

                if created_new_conversation:
                    evt_payload = {"conversation_id": str(conversation.id)}
                    yield format_sse("conversation_created", evt_payload)

                # Load past messages (optional for context)
                message_history = await svc.load_message_history(conversation.id)

                # Fetch content
                content_md = await svc.fetch_markdown_from_url(payload.url)
                if not content_md:
                    error_payload = {
                        "error": "Failed to fetch URL content",
                        "url": payload.url,
                    }
                    yield f"event: error\ndata: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
                    return

                # Build user prompt content
                user_prompt = payload.message

                async def on_complete(result) -> list[str]:
                    events: list[str] = []
                    try:
                        msgs = ModelMessagesTypeAdapter.validate_python(result.new_messages())
                        jsonable_msgs = svc.to_jsonable_messages(msgs)
                        await svc.persist_message_run(conversation, jsonable_msgs)
                        try:
                            await session.commit()
                        except Exception:
                            logger.exception("Failed to commit session after run persistence")
                    except Exception:
                        logger.exception("Failed to persist translation message run")
                    return events

                async for sse_message in stream_agent_text(
                    translate_agent,
                    user_prompt,
                    deps=TranslateDeps(
                        target_lang=payload.target_lang,
                        source_lang=payload.source_lang,
                        content_to_translate=content_md,
                    ),
                    message_history=message_history,
                    on_complete=on_complete,
                ):
                    yield sse_message
        except Exception as exc:
            error_response = {
                "error": "Translate URL execution error",
                "error_type": type(exc).__name__,
                "details": str(exc),
            }
            yield format_sse("error", error_response)

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream; charset=utf-8",
    )


@router.post(
    "/file",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Successful streaming response",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                        "example": (
                            'event: ai_message\ndata: {"chunk": {"content": "Xin chào"}}\n\n'
                        ),
                    }
                }
            },
        },
        422: {"description": "Validation Error"},
    },
)
async def translate_file(
    payload: TranslateFileRequest, current_user: CurrentUser
) -> StreamingResponse:
    async def stream_generator():
        try:
            async with AsyncSessionLocal() as session:
                svc = TranslateService(session)

                conversation = None
                created_new_conversation = False
                if payload.conversation_id is not None:
                    conversation = await svc.get_conversation_by_id(payload.conversation_id)
                if conversation is None:
                    conversation = await svc.create_conversation_with_preset()
                    created_new_conversation = True

                if created_new_conversation:
                    evt_payload = {"conversation_id": str(conversation.id)}
                    yield format_sse("conversation_created", evt_payload)

                message_history = await svc.load_message_history(conversation.id)

                # Extract text from media (first item for MVP)
                safe_media = svc.decode_media_items(payload.media)

                user_prompt = [
                    payload.message,
                    *safe_media,
                ]

                async def on_complete(result) -> list[str]:
                    events: list[str] = []
                    try:
                        msgs = ModelMessagesTypeAdapter.validate_python(result.new_messages())
                        jsonable_msgs = svc.to_jsonable_messages(msgs)
                        await svc.persist_message_run(conversation, jsonable_msgs)
                        try:
                            await session.commit()
                        except Exception:
                            logger.exception("Failed to commit session after run persistence")
                    except Exception:
                        logger.exception("Failed to persist translation message run")
                    return events

                async for sse_message in stream_agent_text(
                    translate_agent,
                    user_prompt,
                    deps=TranslateDeps(
                        target_lang=payload.target_lang, source_lang=payload.source_lang
                    ),
                    message_history=message_history,
                    on_complete=on_complete,
                ):
                    yield sse_message
        except Exception as exc:
            error_response = {
                "error": "Translate File execution error",
                "error_type": type(exc).__name__,
                "details": str(exc),
            }
            yield format_sse("error", error_response)

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream; charset=utf-8",
    )


__all__ = ["router"]
