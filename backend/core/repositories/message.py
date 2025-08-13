from __future__ import annotations

from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.core.models import Message, MessageRole

from .base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create(
        self,
        conversation_id: UUID,
        *,
        role: MessageRole,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata_=metadata,
        )
        await self.add(message)
        await self.flush()
        return message

    async def bulk_create(
        self,
        conversation_id: UUID,
        items: Iterable[tuple[MessageRole, str, Optional[dict]]],
    ) -> list[Message]:
        messages: list[Message] = []
        for role, content, metadata in items:
            messages.append(
                Message(
                    conversation_id=conversation_id,
                    role=role,
                    content=content,
                    metadata_=metadata,
                )
            )
        await self.add_all(messages)
        await self.flush()
        return messages

    async def list_by_conversation(
        self, conversation_id: UUID, *, limit: int | None = None
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_conversation(self, conversation_id: UUID) -> int:
        messages = await self.list_by_conversation(conversation_id)
        for m in messages:
            await self.delete(m)
        await self.commit()
        return len(messages)
