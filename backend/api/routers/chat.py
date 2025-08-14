from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

import logfire
from backend.core.agents.chat.agent import chat_agent
from backend.core.agents.chat.deps import ChatDeps
from backend.core.mixins import ConversationMixin
from backend.core.models import FeatureKey, FeaturePreset
from backend.core.repositories.conversation import ConversationRepository
from backend.core.utils import extract_tool_return_part
from backend.db import AsyncSessionLocal
from backend.settings import settings
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel
from pydantic_ai.messages import ModelMessagesTypeAdapter
from sqlmodel import select

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(ConversationMixin):
    message: str


class ChatResponse(BaseModel):
    answer: str
    model: str


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

        # Avoid relationship lazy-loads in async by prefetching preset keys
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
                                        tv = sub.get("text") or sub.get("content")
                                        if isinstance(tv, str):
                                            tmp.append(tv)
                        if tmp:
                            preview = " ".join(tmp).strip()
                            break
                    if preview:
                        break
            except Exception:
                preview = None

            fk = keys_by_preset_id.get(str(conv.feature_preset_id), FeatureKey.ai_tim_kiem)
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
                conversation_repo = ConversationRepository(session)

                conversation = None
                if payload.conversation_id is not None:
                    conversation = await conversation_repo.get_by_id(payload.conversation_id)

                created_new_conversation = False
                if conversation is None:
                    # Create a conversation with a default feature preset
                    # TODO: accept feature key/params from payload
                    preset = (
                        (
                            await session.execute(
                                select(FeaturePreset).where(
                                    FeaturePreset.key == FeatureKey.ai_tim_kiem
                                )
                            )
                        )
                        .scalars()
                        .first()
                    )
                    if preset is None:
                        # As a fallback, just pick the first preset available
                        stmt = select(FeaturePreset)
                        result = await session.execute(stmt)
                        preset = result.scalars().first()
                    if preset is None:
                        raise RuntimeError("No feature preset available")

                    conversation = await conversation_repo.create(preset)
                    created_new_conversation = True

                if created_new_conversation:
                    evt_payload = {"conversation_id": str(conversation.id)}
                    json_payload = json.dumps(evt_payload, ensure_ascii=False)
                    yield (f"event: conversation_created\ndata: {json_payload}\n\n")

                # No per-message persistence; runs will be stored below

                # Build message history from stored runs
                message_history = []
                try:
                    runs = await conversation_repo.list_message_runs(conversation.id)
                    for r in runs:
                        # r.messages is a Python JSON-ready object (list/dict)
                        msgs = ModelMessagesTypeAdapter.validate_python(r.messages)
                        logfire.info("Message history", msgs=msgs)
                        message_history.extend(msgs)
                except Exception:
                    logger.exception(
                        "Failed to load message history from runs; proceeding without history"
                    )

                async with chat_agent.run_stream(
                    payload.message,
                    deps=ChatDeps(),
                    message_history=message_history,
                ) as result:
                    async for text_piece in result.stream_text(delta=True):
                        response = {
                            "chunk": {"content": text_piece},
                            "model": settings.model_name,
                        }
                        json_payload = json.dumps(response, ensure_ascii=False)
                        sse_message = f"event: ai_message\ndata: {json_payload}\n\n"
                        logger.debug(f"SSE message: {sse_message}")
                        yield sse_message

                    # Persist the structured run for perfect reconstruction
                    try:
                        # Prefer Python-objects for JSONB column
                        msgs_py = ModelMessagesTypeAdapter.validate_python(result.new_messages())
                        # Emit only search_web tool results for frontend UI
                        search_results: list[dict] = []
                        seen_urls: set[str] = set()

                        tool_return_part = extract_tool_return_part(
                            msgs_py,
                            "search_web",
                        )
                        if tool_return_part:
                            content = (
                                tool_return_part.get("content")
                                if isinstance(tool_return_part, dict)
                                else getattr(tool_return_part, "content", None)
                            )
                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict):
                                        url = item.get("url")
                                        if isinstance(url, str) and url in seen_urls:
                                            continue
                                        if isinstance(url, str):
                                            seen_urls.add(url)
                                            search_results.append(item)

                        if search_results:
                            evt_payload = {"results": search_results}
                            evt_payload_json = json.dumps(evt_payload, ensure_ascii=False)
                            logger.debug(f"SSE search_results message: {evt_payload_json}")
                            yield (f"event: search_results\ndata: {evt_payload_json}\n\n")

                        # Convert to jsonable python to avoid non-serializables
                        from pydantic_core import to_jsonable_python

                        msgs_py = to_jsonable_python(msgs_py)
                        await conversation_repo.add_message_run(
                            conversation,
                            msgs_py,
                        )
                    except Exception:
                        logger.exception("Failed to persist conversation message run")

                    # Commit after run persistence
                    try:
                        await session.commit()
                    except Exception:
                        logger.exception("Failed to commit session after run persistence")
        except Exception as exc:
            error_response = {
                "error": "Chat execution error",
                "error_type": type(exc).__name__,
                "details": str(exc),
            }
            json_payload = json.dumps(
                error_response,
                ensure_ascii=False,
            )
            yield f"event: error\ndata: {json_payload}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream; charset=utf-8",
    )


@router.get("/{conversation_id}")
async def get_conversation_history(conversation_id: UUID) -> dict:
    """Return flattened message history for a conversation."""
    async with AsyncSessionLocal() as session:
        conversation_repo = ConversationRepository(session)
        conversation = await conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            )

        messages: list[dict[str, str]] = []
        runs = await conversation_repo.list_message_runs(conversation_id)

        for run in runs:
            try:
                objs = ModelMessagesTypeAdapter.validate_python(run.messages)
            except Exception:
                objs = []

            for msg in objs:
                kind = msg.get("kind") if isinstance(msg, dict) else getattr(msg, "kind", None)
                parts = msg.get("parts") if isinstance(msg, dict) else getattr(msg, "parts", None)
                if not isinstance(parts, list):
                    continue

                text: str = ""
                if kind == "request":
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
                            text = cval
                        elif isinstance(cval, list):
                            tmp: list[str] = []
                            for sub in cval:
                                if isinstance(sub, str):
                                    tmp.append(sub)
                                elif isinstance(sub, dict):
                                    tv = sub.get("text") or sub.get("content")
                                    if isinstance(tv, str):
                                        tmp.append(tv)
                            text = "\n".join(tmp)
                        break
                    if text:
                        messages.append(
                            {
                                "role": "user",
                                "content": text,
                            }
                        )
                elif kind == "response":
                    tmp: list[str] = []
                    for part in parts:
                        pk = (
                            part.get("part_kind")
                            if isinstance(part, dict)
                            else getattr(part, "part_kind", None)
                        )
                        if pk != "text":
                            continue
                        tv = (
                            part.get("content")
                            if isinstance(part, dict)
                            else getattr(part, "content", None)
                        )
                        if not isinstance(tv, str):
                            tv = (
                                part.get("text")
                                if isinstance(part, dict)
                                else getattr(part, "text", None)
                            )
                        if isinstance(tv, str):
                            tmp.append(tv)
                    text = "\n".join(tmp)
                    if text:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": text,
                            }
                        )

        logfire.info("Messages:", messages=messages)
        return {
            "conversation_id": str(conversation_id),
            "messages": messages,
        }


__all__ = ["router"]
