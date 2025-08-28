from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

import logfire
from backend.api.routers.models.responses import ConversationHistoryResponse
from backend.core.agents.chat.agent import chat_agent
from backend.core.agents.chat.deps import ChatDeps
from backend.core.mixins import ConversationMixin
from backend.core.models import FeatureKey, FeaturePreset
from backend.core.repositories.conversation import ConversationRepository
from backend.core.services.base import BinaryContentIn
from backend.core.services.chat import ChatService
from backend.core.services.streaming import format_sse, stream_agent_text
from backend.db import AsyncSessionLocal
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field
from pydantic_ai.messages import ModelMessagesTypeAdapter
from sqlmodel import select

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(ConversationMixin):
    message: str
    media: Optional[list[BinaryContentIn]] = Field(default_factory=list)


class ConversationListItem(BaseModel):
    id: str
    feature_key: FeatureKey
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    content_preview: str | None = None


@router.get("", response_model=dict[str, list[ConversationListItem]])
async def list_conversations() -> dict[str, list[ConversationListItem]]:
    """List all conversations with a brief preview."""
    async with AsyncSessionLocal() as session:
        conversation_repo = ConversationRepository(session)
        conversations = await conversation_repo.list_all()

        # Avoid lazy-loads in async by prefetching preset keys
        preset_ids = {c.feature_preset_id for c in conversations}
        keys_by_preset_id: dict[str, FeatureKey] = {}
        if preset_ids:
            rows = await session.execute(
                select(FeaturePreset.id, FeaturePreset.key).where(FeaturePreset.id.in_(preset_ids))
            )
            for pid, key in rows.all():
                keys_by_preset_id[str(pid)] = key

        items: list[ConversationListItem] = []

        # Build previews by scanning latest runs per conversation (best-effort)
        for conv in conversations:
            preview: str | None = None
            try:
                runs = await conversation_repo.list_message_runs(conv.id)
                for run in reversed(runs):
                    try:
                        objs = ModelMessagesTypeAdapter.validate_python(run.messages)
                    except Exception:
                        objs = []
                    # find last user prompt in this run
                    for msg in reversed(list(objs)):
                        kind = (
                            msg.get("kind") if isinstance(msg, dict) else getattr(msg, "kind", None)
                        )
                        if kind != "request":
                            continue
                        parts = (
                            msg.get("parts")
                            if isinstance(msg, dict)
                            else getattr(msg, "parts", None)
                        )
                        if not isinstance(parts, list):
                            continue
                        tmp: list[str] = []
                        for part in parts:
                            pk = (
                                part.get("part_kind")
                                if isinstance(part, dict)
                                else getattr(part, "part_kind", None)
                            )
                            if pk != "user-prompt":
                                continue
                            cval = (
                                part.get("content")
                                if isinstance(part, dict)
                                else getattr(part, "content", None)
                            )
                            if isinstance(cval, str):
                                tmp.append(cval)
                            elif isinstance(cval, list):
                                for sub in cval:
                                    if isinstance(sub, str):
                                        tmp.append(sub)
                                    elif isinstance(sub, dict):
                                        text_val = sub.get("text")
                                        content_val = sub.get("content")
                                        tv = text_val or content_val
                                        if isinstance(tv, str):
                                            tmp.append(tv)
                        if tmp:
                            preview = " ".join(tmp).strip()
                            break
                    if preview:
                        break
            except Exception:
                preview = None

            fk = keys_by_preset_id.get(
                str(conv.feature_preset_id),
                FeatureKey.ai_tim_kiem,
            )
            items.append(
                ConversationListItem(
                    id=str(conv.id),
                    feature_key=fk,
                    title=conv.title,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                    content_preview=preview,
                )
            )

        logfire.info("Conversations", items=items)
        return {"items": items}


@router.post(
    "",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Successful streaming response",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                        "example": ('event: ai_message\ndata: {"chunk": {"content": "Hi"}}\n\n'),
                    }
                }
            },
        },
        422: {"description": "Validation Error"},
    },
)
async def chat(payload: ChatRequest) -> StreamingResponse:
    async def stream_generator():
        try:
            async with AsyncSessionLocal() as session:
                chat_service = ChatService(session)

                # Resolve existing conversation or create a new one
                conversation = None
                created_new_conversation = False
                if payload.conversation_id is not None:
                    conversation = await chat_service.get_conversation_by_id(
                        payload.conversation_id
                    )
                if conversation is None:
                    create_default = chat_service.create_conversation_with_default_preset
                    conversation = await create_default()
                    created_new_conversation = True

                if created_new_conversation:
                    evt_payload = {"conversation_id": str(conversation.id)}
                    yield format_sse("conversation_created", evt_payload)

                # Load message history
                message_history = await chat_service.load_message_history(conversation.id)

                # Decode media and build user content
                safe_media = chat_service.decode_media_items(payload.media)
                user_prompt = [payload.message, *safe_media]

                async def on_complete(result) -> list[str]:
                    events: list[str] = []
                    try:
                        msgs = ModelMessagesTypeAdapter.validate_python(result.new_messages())
                        search_results = chat_service.extract_search_results(msgs, "search_web")
                        fetch_url_results = chat_service.extract_search_results(
                            msgs, "fetch_url_content"
                        )
                        jsonable_msgs = chat_service.to_jsonable_messages(msgs)
                        await chat_service.persist_message_run(conversation, jsonable_msgs)

                        if search_results:
                            events.append(format_sse("search_results", {"results": search_results}))
                        if fetch_url_results:
                            events.append(
                                format_sse("fetch_url_results", {"results": fetch_url_results})
                            )
                        try:
                            await session.commit()
                        except Exception:
                            logger.exception("Failed to commit session after run persistence")
                    except Exception:
                        logger.exception("Failed to persist conversation message run")
                    return events

                async for sse_message in stream_agent_text(
                    chat_agent,
                    user_prompt,
                    deps=ChatDeps(),
                    message_history=message_history,
                    on_complete=on_complete,
                ):
                    yield sse_message
        except Exception as exc:
            error_response = {
                "error": "Chat execution error",
                "error_type": type(exc).__name__,
                "details": str(exc),
            }
            yield format_sse("error", error_response)

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream; charset=utf-8",
    )


@router.get("/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation_history(conversation_id: UUID) -> dict:
    """Return flattened message history for a conversation."""
    async with AsyncSessionLocal() as session:
        chat_service = ChatService(session)
        conversation = await chat_service.conversation_repo.get_by_id(conversation_id)

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            )

        json_safe_parts = await chat_service.serialize_history(conversation_id)

        logfire.info("Messages", messages=json_safe_parts)
        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            messages=json_safe_parts,
        )


__all__ = ["router"]
