from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel, select

from backend.core.models import FeatureKey, FeaturePreset
from backend.settings import settings


def _to_async_url(url: str) -> str:
    # Normalize URL to async driver without forcing the user to change envs
    if url.startswith("postgresql+asyncpg://") or url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return url.replace("postgresql://", "postgresql+psycopg://").replace(
            "postgres://", "postgresql+psycopg://"
        )
    return url


async_engine: AsyncEngine = create_async_engine(
    _to_async_url(settings.database_url),
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, expire_on_commit=False, class_=AsyncSession
)


async def drop_all() -> None:
    """Drop all tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


async def create_all() -> None:
    # Ensure required extensions exist before creating tables
    async with async_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
        await conn.run_sync(SQLModel.metadata.create_all)


async def seed_feature_presets() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(FeaturePreset))
        existing = {fp.key for fp in result.scalars().all()}
        seeds = [
            FeaturePreset(
                key=FeatureKey.ai_tim_kiem,
                name="AI Tìm kiếm",
                system_prompt=(
                    "Bạn là trợ lý AI trả lời ngắn gọn, dẫn nguồn báo chí Việt Nam khi có."
                ),
                default_params={},
            ),
            FeaturePreset(
                key=FeatureKey.giai_bai_tap,
                name="Giải bài tập",
                system_prompt=("Bạn là trợ giảng giải thích từng bước, có ví dụ và kiểm tra lại."),
                default_params={"show_steps": True},
            ),
            FeaturePreset(
                key=FeatureKey.ai_viet_van,
                name="AI viết văn",
                system_prompt=("Bạn là biên tập viên viết tiếng Việt tự nhiên, mạch lạc."),
                default_params={"length": "medium", "tone": "trung_lap"},
            ),
            FeaturePreset(
                key=FeatureKey.dich,
                name="Dịch",
                system_prompt=("Bạn là dịch giả, giữ nguyên tên riêng và thuật ngữ."),
                default_params={
                    "source_lang": "vi",
                    "target_lang": "en",
                },
            ),
            FeaturePreset(
                key=FeatureKey.tom_tat,
                name="Tóm tắt",
                system_prompt=("Tóm tắt trọng tâm, có gạch đầu dòng."),
                default_params={"bullet_count": 5},
            ),
            FeaturePreset(
                key=FeatureKey.mindmap,
                name="Mindmap",
                system_prompt=("Trả về cấu trúc chủ đề dạng cây."),
                default_params={"max_depth": 3},
            ),
        ]

        new_items = [s for s in seeds if s.key not in existing]
        if new_items:
            session.add_all(new_items)
            await session.commit()
            print(f"Seeded {len(new_items)} feature presets.")
        else:
            print("Feature presets already present, skipping.")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def main() -> None:
    print("Dropping existing tables...")
    await drop_all()
    print("Creating tables...")
    await create_all()
    print("Seeding presets...")
    await seed_feature_presets()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
