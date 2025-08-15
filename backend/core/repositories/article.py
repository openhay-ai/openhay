from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Optional

from backend.core.models import Article
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from .base import BaseRepository


class ArticleRepository(BaseRepository[Article]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_url(self, url: str) -> Optional[Article]:
        stmt = select(Article).where(Article.url == url)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def upsert_many(self, articles: Iterable[Article]) -> list[Article]:
        stored: list[Article] = []
        for a in articles:
            existing = await self.get_by_url(a.url)
            if existing:
                # update minimal fields if missing
                existing.title = existing.title or a.title
                existing.author = existing.author or a.author
                existing.image_url = existing.image_url or a.image_url
                existing.published_at = existing.published_at or a.published_at
                existing.content_text = existing.content_text or a.content_text
                stored.append(existing)
            else:
                await self.add(a)
                stored.append(a)
        await self.flush()
        return stored

    async def list_by_day(self, target_day: date) -> list[Article]:
        start = datetime.combine(target_day, datetime.min.time())
        end = datetime.combine(target_day, datetime.max.time())
        stmt = (
            select(Article)
            .where(col(Article.fetched_at).between(start, end))
            .order_by(Article.fetched_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
