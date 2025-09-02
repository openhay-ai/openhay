from __future__ import annotations

from datetime import date
from typing import Iterable, Optional
from uuid import UUID

from backend.core.models import DailySuggestion
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from .base import BaseRepository


class DailySuggestionRepository(BaseRepository[DailySuggestion]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_for_day(self, d: date) -> list[DailySuggestion]:
        stmt = (
            select(DailySuggestion)
            .where(DailySuggestion.suggestion_date == d)
            .order_by(DailySuggestion.rank.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_for_article_and_day(self, article_id: UUID, d: date) -> Optional[DailySuggestion]:
        stmt = select(DailySuggestion).where(
            DailySuggestion.article_id == article_id,
            DailySuggestion.suggestion_date == d,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def upsert_many(self, suggestions: Iterable[DailySuggestion]) -> list[DailySuggestion]:
        stored: list[DailySuggestion] = []
        for s in suggestions:
            existing = await self.get_for_article_and_day(s.article_id, s.suggestion_date)
            if existing:
                existing.rank = min(existing.rank, s.rank)
                existing.reason = existing.reason or s.reason
                stored.append(existing)
            else:
                await self.add(s)
                stored.append(s)
        await self.flush()
        return stored

    async def get_last_day(self) -> Optional[date]:
        stmt = (
            select(DailySuggestion.suggestion_date)
            .order_by(DailySuggestion.suggestion_date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
