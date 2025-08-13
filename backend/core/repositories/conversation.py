from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.core.models import (
    Conversation,
    ConversationMessageRun,
    FeaturePreset,
    Message,
)

from .base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # Conversation CRUD
    async def create(
        self,
        feature_preset: FeaturePreset,
        *,
        title: Optional[str] = None,
        feature_params: Optional[dict] = None,
    ) -> Conversation:
        conversation = Conversation(
            feature_preset_id=feature_preset.id,
            title=title,
            feature_params=feature_params or {},
        )
        await self.add(conversation)
        await self.flush()
        return conversation

    async def get_by_id(self, conversation_id: UUID) -> Optional[Conversation]:
        return await self.session.get(Conversation, conversation_id)

    async def list_by_feature_preset(self, feature_preset_id: UUID) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.feature_preset_id == feature_preset_id)
            .order_by(Conversation.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[Conversation]:
        stmt = select(Conversation).order_by(Conversation.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_title(self, conversation: Conversation, title: Optional[str]) -> Conversation:
        conversation.title = title
        conversation.updated_at = datetime.utcnow()
        await self.flush()
        await self.refresh(conversation)
        return conversation

    async def update_feature_params(self, conversation: Conversation, params: dict) -> Conversation:
        conversation.feature_params = params
        conversation.updated_at = datetime.utcnow()
        await self.flush()
        await self.refresh(conversation)
        return conversation

    async def delete_conversation(self, conversation: Conversation) -> None:
        await self.delete(conversation)
        await self.commit()

    # Messaging helpers related to a conversation
    async def add_messages(
        self, conversation: Conversation, messages: Iterable[Message]
    ) -> list[Message]:
        for m in messages:
            m.conversation_id = conversation.id
            await self.add(m)
        await self.flush()
        return list(messages)

    # Conversation message runs
    async def add_message_run(
        self, conversation: Conversation, messages_obj: dict | list
    ) -> ConversationMessageRun:
        run = ConversationMessageRun(conversation_id=conversation.id, messages=messages_obj)
        await self.add(run)
        await self.flush()
        await self.refresh(run)
        return run

    async def list_message_runs(self, conversation_id: UUID) -> list[ConversationMessageRun]:
        stmt = (
            select(ConversationMessageRun)
            .where(ConversationMessageRun.conversation_id == conversation_id)
            .order_by(ConversationMessageRun.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
