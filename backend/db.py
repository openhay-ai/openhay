from __future__ import annotations

import os
from datetime import date  # noqa: F401  (reserved for future seeds)

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from backend.core.models import FeatureKey, FeaturePreset
from backend.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)


def create_all() -> None:
    # Ensure required extensions exist before creating tables
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
    SQLModel.metadata.create_all(engine)


def seed_feature_presets() -> None:
    with Session(engine) as session:
        existing = {fp.key for fp in session.exec(select(FeaturePreset)).all()}
        seeds = [
            FeaturePreset(
                key=FeatureKey.ai_tim_kiem,
                name="AI Tìm kiếm",
                system_prompt=(
                    "Bạn là trợ lý AI trả lời ngắn gọn,"
                    " dẫn nguồn báo chí Việt Nam"
                    " khi có."
                ),
                default_params={},
            ),
            FeaturePreset(
                key=FeatureKey.giai_bai_tap,
                name="Giải bài tập",
                system_prompt=(
                    "Bạn là trợ giảng giải thích từng bước, có ví dụ và"
                    " kiểm tra lại."
                ),
                default_params={"show_steps": True},
            ),
            FeaturePreset(
                key=FeatureKey.ai_viet_van,
                name="AI viết văn",
                system_prompt=(
                    "Bạn là biên tập viên viết tiếng Việt tự nhiên, mạch lạc."
                ),
                default_params={"length": "medium", "tone": "trung_lap"},
            ),
            FeaturePreset(
                key=FeatureKey.dich,
                name="Dịch",
                system_prompt=("Bạn là dịch giả, giữ nguyên tên riêng và thuật ngữ."),
                default_params={"source_lang": "vi", "target_lang": "en"},
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
            session.commit()
            print(f"Seeded {len(new_items)} feature presets.")
        else:
            print("Feature presets already present, skipping.")


def get_session():
    with Session(engine) as session:
        yield session


def main() -> None:
    print("Creating tables...")
    create_all()
    print("Seeding presets...")
    seed_feature_presets()
    print("Done.")


if __name__ == "__main__":
    main()
