from __future__ import annotations

import base64
from typing import Optional

import logfire
from backend.core.repositories.conversation import ConversationRepository
from backend.core.utils import extract_tool_return_parts
from loguru import logger
from pydantic import BaseModel
from pydantic_ai import BinaryContent
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from pydantic_core import to_jsonable_python
from sqlalchemy.ext.asyncio import AsyncSession


class BinaryContentIn(BaseModel):
    data: str
    media_type: str
    identifier: str | None = None


class BaseConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conversation_repo = ConversationRepository(session)

    async def get_conversation_by_id(self, conversation_id) -> object | None:
        return await self.conversation_repo.get_by_id(conversation_id)

    async def load_message_history(self, conversation_id) -> list[ModelMessage]:
        message_history: list[ModelMessage] = []
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

    async def persist_message_run(
        self, conversation: object, jsonable_messages: list | dict
    ) -> None:
        await self.conversation_repo.add_message_run(conversation, jsonable_messages)

    def to_jsonable_messages(self, messages: list[ModelMessage]) -> list | dict:
        return to_jsonable_python(messages, bytes_mode="base64")

    def decode_media_items(self, media: Optional[list[BinaryContentIn]]) -> list[BinaryContent]:
        safe_media: list[BinaryContent] = []
        for item in media or []:
            try:
                raw_bytes = self._b64_to_bytes(item.data)
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

    def extract_search_results(self, messages: list[ModelMessage], tool_name: str) -> list[dict]:
        search_results: list[dict] = []
        seen_urls: set[str] = set()

        tool_return_parts = extract_tool_return_parts(messages, tool_name)
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

    async def serialize_history(self, conversation_id) -> list[dict]:
        runs = await self.conversation_repo.list_message_runs(conversation_id)
        json_safe_parts: list[dict] = []
        for run in runs:
            try:
                messages = ModelMessagesTypeAdapter.validate_python(run.messages)
                parts = [part for message in messages for part in message.parts]
                parts_json = to_jsonable_python(parts, bytes_mode="base64")
                for p in parts_json:
                    if isinstance(p, dict):
                        json_safe_parts.append(p)
            except Exception:
                logger.exception("Failed to serialize history run; skipping")
                continue
        return json_safe_parts

    @staticmethod
    def _b64_to_bytes(data: str) -> bytes:
        try:
            return base64.b64decode(data)
        except Exception:
            normalized = data.replace("-", "+").replace("_", "/")
            pad = (-len(normalized)) % 4
            if pad:
                normalized += "=" * pad
            return base64.b64decode(normalized)


__all__ = ["BinaryContentIn", "BaseConversationService"]
