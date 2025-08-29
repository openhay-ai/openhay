from __future__ import annotations

from backend.core.models import Conversation, FeatureKey, FeaturePreset
from backend.core.services.base import BaseConversationService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select


class ChatService(BaseConversationService):
    """Service layer for chat operations.

    Responsibilities are split into single-purpose methods to keep
    each function focused and easy to test.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_conversation_with_default_preset(self) -> Conversation:
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


__all__ = [
    "ChatService",
]
