from __future__ import annotations

from typing import Optional

from backend.core.models import ArticleSource
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from .base import BaseRepository


class ArticleSourceRepository(BaseRepository[ArticleSource]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_domain(self, domain: str) -> Optional[ArticleSource]:
        stmt = select(ArticleSource).where(ArticleSource.domain == domain)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_or_create(
        self,
        *,
        domain: str,
        name: Optional[str] = None,
        homepage_url: Optional[str] = None,
    ) -> ArticleSource:
        existing = await self.get_by_domain(domain)
        if existing:
            return existing
        src = ArticleSource(domain=domain, name=name or domain, homepage_url=homepage_url)
        await self.add(src)
        await self.flush()
        await self.refresh(src)
        return src
