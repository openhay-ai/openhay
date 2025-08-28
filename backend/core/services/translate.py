from __future__ import annotations

import base64
from typing import Optional
from uuid import UUID

import logfire
from backend.core.models import Conversation, FeatureKey, FeaturePreset
from backend.core.repositories.conversation import ConversationRepository
from backend.core.services.chat import BinaryContent, BinaryContentIn
from backend.core.tools.search import fetch_url
from loguru import logger
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from pydantic_core import to_jsonable_python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select


class TranslateService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conversation_repo = ConversationRepository(session)

    async def get_conversation_by_id(self, conversation_id: UUID) -> object | None:
        return await self.conversation_repo.get_by_id(conversation_id)

    async def create_conversation_with_preset(self) -> Conversation:
        preset = (
            (
                await self.session.execute(
                    select(FeaturePreset).where(FeaturePreset.key == FeatureKey.dich)
                )
            )
            .scalars()
            .first()
        )
        if preset is None:
            stmt = select(FeaturePreset)
            result = await self.session.execute(stmt)
            preset = result.scalars().first()
        if preset is None:
            raise RuntimeError("No feature preset available")

        conversation = await self.conversation_repo.create(preset)
        return conversation

    async def load_message_history(self, conversation_id: UUID) -> list[ModelMessage]:
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

    async def fetch_markdown_from_url(self, url: str) -> str | None:
        try:
            results = await fetch_url(
                [url], ignore_links=True, ignore_images=True, escape_html=True, pruned=True
            )
            if not results:
                return None
            return results[0].get("content")
        except Exception:
            logger.exception("Failed to fetch URL content")
            return None

    def extract_text_from_media(self, media: Optional[list[BinaryContentIn]]) -> str:
        if not media:
            return ""
        # MVP: assume first item is the primary content; try to decode as UTF-8 text
        item = media[0]
        raw_bytes = self._b64_to_bytes(item.data)
        try:
            text = raw_bytes.decode("utf-8", errors="replace")
            logger.info(f"Text: {text}")
            return text
        except Exception:
            logger.exception("Failed to decode media as utf-8 text")
            return ""

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
