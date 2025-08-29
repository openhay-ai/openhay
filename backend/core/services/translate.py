from __future__ import annotations

from typing import Optional

from backend.core.models import Conversation, FeatureKey, FeaturePreset
from backend.core.services.base import BaseConversationService, BinaryContentIn
from backend.core.tools.search import fetch_url
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select


class TranslateService(BaseConversationService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

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
