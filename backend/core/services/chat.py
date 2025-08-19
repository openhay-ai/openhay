from __future__ import annotations

import base64
from typing import Optional
from uuid import UUID

import logfire
from backend.core.models import FeatureKey, FeaturePreset
from backend.core.repositories.conversation import ConversationRepository
from backend.core.utils import extract_tool_return_parts
from loguru import logger
from pydantic import BaseModel
from pydantic_ai import BinaryContent
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from pydantic_core import to_jsonable_python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select


class BinaryContentIn(BaseModel):
    """Incoming media item with base64-encoded data from the frontend.

    We explicitly accept base64 here and decode to raw bytes before
    constructing pydantic-ai's BinaryContent.
    """

    data: str
    media_type: str
    identifier: str | None = None


class ChatService:
    """Service layer for chat operations.

    Responsibilities are split into single-purpose methods to keep
    each function focused and easy to test.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conversation_repo = ConversationRepository(session)

    async def get_conversation_by_id(self, conversation_id: UUID) -> object | None:
        """Return conversation by id or None."""
        return await self.conversation_repo.get_by_id(conversation_id)

    async def create_conversation_with_default_preset(self) -> object:
        """Create a new conversation using the default preset.

        Falls back to the first available preset if the default is
        missing.
        """
        preset = (
            (
                await self.session.execute(
                    select(FeaturePreset).where(FeaturePreset.key == FeatureKey.ai_tim_kiem)
                )
            )
            .scalars()
            .first()
        )
        if preset is None:
            # Fallback: pick the first available preset
            stmt = select(FeaturePreset)
            result = await self.session.execute(stmt)
            preset = result.scalars().first()
        if preset is None:
            raise RuntimeError("No feature preset available")

        conversation = await self.conversation_repo.create(preset)
        return conversation

    async def load_message_history(self, conversation_id: UUID) -> list[ModelMessage]:
        """Load message history from stored conversation runs."""
        message_history = []
        try:
            runs = await self.conversation_repo.list_message_runs(conversation_id)
            for r in runs:
                msgs = ModelMessagesTypeAdapter.validate_python(r.messages)
                logfire.info("Message history", msgs=msgs)
                message_history.extend(msgs)
        except Exception:
            logger.exception(
                ("Failed to load message history from runs; proceeding without history")
            )
        return message_history

    def decode_media_items(self, media: Optional[list[BinaryContentIn]]) -> list[BinaryContent]:
        """Decode base64 media items to BinaryContent objects."""
        safe_media: list[BinaryContent] = []
        for item in media or []:
            try:
                raw_bytes = self._b64_to_bytes(item.data)
            except Exception:
                # If decode fails, skip item
                logger.exception("Failed to decode base64 media item; skipping")
                continue

            safe_media.append(
                BinaryContent(
                    data=raw_bytes,
                    media_type=item.media_type,
                    identifier=item.identifier,
                )
            )
        return safe_media

    def extract_search_results(self, messages: list[ModelMessage]) -> list[dict]:
        """Extract and deduplicate search results."""
        search_results: list[dict] = []
        seen_urls: set[str] = set()

        tool_return_parts = extract_tool_return_parts(messages, "search_web")
        if tool_return_parts:
            for tool_return_part in tool_return_parts:
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
        return search_results

    def extract_fetch_url_results(self, messages: list[ModelMessage]) -> list[dict]:
        """Extract and deduplicate fetch URL results."""
        fetch_results: list[dict] = []
        seen_urls: set[str] = set()

        tool_return_parts = extract_tool_return_parts(messages, "fetch_url_content")
        if tool_return_parts:
            for tool_return_part in tool_return_parts:
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
                                fetch_results.append(item)
        return fetch_results

    def to_jsonable_messages(self, messages: list[ModelMessage]) -> list | dict:
        """Convert messages to JSON-safe python objects.

        Bytes are encoded as base64.
        """
        return to_jsonable_python(messages, bytes_mode="base64")

    async def persist_message_run(
        self, conversation: object, jsonable_messages: list | dict
    ) -> None:
        """Persist a message run for a conversation."""
        await self.conversation_repo.add_message_run(conversation, jsonable_messages)

    async def serialize_history(self, conversation_id: UUID) -> list[dict]:
        """Serialize conversation history as JSON-safe parts."""
        runs = await self.conversation_repo.list_message_runs(conversation_id)

        # Build a JSON-safe list of parts with bytes encoded as base64
        json_safe_parts: list[dict] = []
        for run in runs:
            try:
                messages = ModelMessagesTypeAdapter.validate_python(run.messages)
                # Flatten parts across messages
                parts = [part for message in messages for part in message.parts]
                parts_json = to_jsonable_python(parts, bytes_mode="base64")
                # Ensure each part is a dict for response model typing
                for p in parts_json:
                    if isinstance(p, dict):
                        json_safe_parts.append(p)
            except Exception:
                # If any run is malformed, skip that run
                logger.exception("Failed to serialize history run; skipping")
                continue

        return json_safe_parts

    @staticmethod
    def _b64_to_bytes(data: str) -> bytes:
        """Decode either standard base64 or base64url ("-_/" variant).

        Adds required padding if missing.
        """
        try:
            # Fast path: try regular b64
            return base64.b64decode(data)
        except Exception:
            # Normalize URL-safe alphabet and pad
            normalized = data.replace("-", "+").replace("_", "/")
            pad = (-len(normalized)) % 4
            if pad:
                normalized += "=" * pad
            return base64.b64decode(normalized)


async def load_message_history(
    conversation_repo: ConversationRepository, conversation_id: UUID
) -> list[ModelMessage]:
    """Backward compatibility function."""
    # This requires the session from the repo, which we don't have access to
    # For now, we'll keep this as a wrapper but service should be used
    runs = await conversation_repo.list_message_runs(conversation_id)
    message_history = []
    for r in runs:
        msgs = ModelMessagesTypeAdapter.validate_python(r.messages)
        logfire.info("Message history", msgs=msgs)
        message_history.extend(msgs)
    return message_history


def decode_media_items(media: Optional[list[BinaryContentIn]]) -> list[BinaryContent]:
    """Backward compatibility function."""
    safe_media: list[BinaryContent] = []
    for item in media or []:
        try:
            raw_bytes = ChatService._b64_to_bytes(item.data)
        except Exception:
            logger.exception("Failed to decode base64 media item; skipping")
            continue

        safe_media.append(
            BinaryContent(
                data=raw_bytes,
                media_type=item.media_type,
                identifier=item.identifier,
            )
        )
    return safe_media


def extract_search_results(messages: list[ModelMessage]) -> list[dict]:
    """Backward compatibility function."""
    search_results: list[dict] = []
    seen_urls: set[str] = set()

    tool_return_parts = extract_tool_return_parts(messages, "search_web")
    if tool_return_parts:
        for tool_return_part in tool_return_parts:
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
    return search_results


async def serialize_history(
    conversation_repo: ConversationRepository, conversation_id: UUID
) -> list[dict]:
    """Backward compatibility function."""
    runs = await conversation_repo.list_message_runs(conversation_id)

    # Build a JSON-safe list of parts with bytes encoded as base64
    json_safe_parts: list[dict] = []
    for run in runs:
        try:
            messages = ModelMessagesTypeAdapter.validate_python(run.messages)
            # Flatten parts across messages
            parts = [part for message in messages for part in message.parts]
            parts_json = to_jsonable_python(parts, bytes_mode="base64")
            # Ensure each part is a dict for response model typing
            for p in parts_json:
                if isinstance(p, dict):
                    json_safe_parts.append(p)
        except Exception:
            # If any run is malformed, skip that run
            logger.exception("Failed to serialize history run; skipping")
            continue

    return json_safe_parts


__all__ = [
    "BinaryContentIn",
    "ChatService",
    "load_message_history",
    "decode_media_items",
    "extract_search_results",
    "serialize_history",
]
