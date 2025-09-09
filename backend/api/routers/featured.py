from __future__ import annotations

from datetime import date, datetime
from urllib.parse import urlparse

from backend.core.agents.discover.agent import discover_best_posts
from backend.core.models import Article, DailySuggestion
from backend.core.repositories import (
    ArticleRepository,
    ArticleSourceRepository,
    DailySuggestionRepository,
)
from backend.db import AsyncSessionLocal
from fastapi import APIRouter, BackgroundTasks
from loguru import logger
from sqlalchemy import text

router = APIRouter(prefix="/api/featured", tags=["featured"])


@router.get("")
async def get_today_featured(
    background_tasks: BackgroundTasks,
) -> dict[str, list[dict]]:
    # Use local time to avoid timezone issues
    now = datetime.now()
    today = now.date()

    async with AsyncSessionLocal() as session:
        sug_repo = DailySuggestionRepository(session)
        art_repo = ArticleRepository(session)

        existing_today = await sug_repo.list_for_day(today)
        last_day = await sug_repo.get_last_day()

        # Decide which day to use for response and whether to kick off/wait
        if existing_today:
            cnt = len(existing_today)
            msg = f"Found {cnt} existing featured items for {today}"
            logger.info(msg)
            use_suggestions = existing_today
        else:
            cutoff = now.replace(hour=6, minute=0, second=0, microsecond=0)
            if now >= cutoff:
                # Distributed single-flight using Postgres advisory lock
                lock_key = f"featured:{today.isoformat()}"
                async with AsyncSessionLocal() as lock_session:
                    async with lock_session.bind.connect() as conn:
                        res = await conn.execute(
                            text("SELECT pg_try_advisory_lock(hashtext(:k)::bigint)"),
                            {"k": lock_key},
                        )
                        acquired = bool(res.scalar())

                        if acquired:
                            logger.info("Acquired lock; schedule generation")
                            try:
                                # Trigger background generation and return
                                # latest available items
                                background_tasks.add_task(
                                    generate_today_featured,
                                    today,
                                )
                            finally:
                                await conn.execute(
                                    text("SELECT pg_advisory_unlock(hashtext(:k)::bigint)"),
                                    {"k": lock_key},
                                )
                            use_suggestions = await sug_repo.list_for_day(today)
                            if use_suggestions:
                                cnt = len(use_suggestions)
                                logger.info(
                                    "Returning {} items for {}",
                                    cnt,
                                    today,
                                )
                            else:
                                if last_day:
                                    yesterday_featured = await sug_repo.list_for_day(last_day)
                                    cnt = len(yesterday_featured)
                                    logger.info(
                                        "Not ready; return {} for {}",
                                        cnt,
                                        last_day,
                                    )
                                    use_suggestions = yesterday_featured
                                else:
                                    logger.info(
                                        "No previous featured available; returning empty list"
                                    )
                                    use_suggestions = []
                        else:
                            logger.info("Worker generating; waiting...")

                            # Fallback to latest available day if not ready
                            if last_day:
                                yesterday_featured = await sug_repo.list_for_day(last_day)
                                cnt = len(yesterday_featured)
                                logger.info(
                                    "Timeout; return {} for {}",
                                    cnt,
                                    last_day,
                                )
                                use_suggestions = yesterday_featured
                            else:
                                logger.info("No previous featured available; returning empty list")
                                use_suggestions = []
            else:
                # Before cutoff, do not generate yet; use yesterday's
                if last_day:
                    yesterday_featured = await sug_repo.list_for_day(last_day)
                    cnt = len(yesterday_featured)
                    logger.info(
                        "Returning {} featured items for {} (before cutoff)",
                        cnt,
                        last_day,
                    )
                    use_suggestions = yesterday_featured
                else:
                    logger.info(
                        "No previous featured available before cutoff; returning empty list"
                    )
                    use_suggestions = []

        # Join with articles by explicit IDs to avoid filtering by fetched_at
        article_ids = [s.article_id for s in use_suggestions]
        articles = await art_repo.list_by_ids(article_ids)
        article_by_id = {a.id: a for a in articles}

        items: list[dict] = []
        for s in use_suggestions:
            a = article_by_id.get(s.article_id)
            if not a:
                continue
            items.append(
                {
                    "title": a.title,
                    "url": a.url,
                    "image_url": a.image_url,
                    "summary": s.reason or a.content_text,
                    "source": urlparse(a.url).hostname or "",
                    "published_at": (a.published_at.isoformat() if a.published_at else None),
                }
            )

        return {"items": items}


async def generate_today_featured(target_day: date) -> list[dict]:
    # Use discover agent to collect best posts from configured sources
    discovered = await discover_best_posts()

    # Deduplicate by URL while preserving order
    seen_urls: set[str] = set()
    items: list[dict] = []
    for r in discovered:
        url = (r.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        items.append(
            {
                "url": url,
                "title": r.get("title") or "",
                "image_url": r.get("image_url") or None,
                "content": r.get("content") or "",
                "description": r.get("description") or "",
                "metadata": r.get("metadata") or {},
            }
        )

    # Persist all discovered items
    async with AsyncSessionLocal() as session:
        src_repo = ArticleSourceRepository(session)
        art_repo = ArticleRepository(session)
        sug_repo = DailySuggestionRepository(session)

        articles_to_store: list[Article] = []
        suggestions_to_store: list[DailySuggestion] = []

        for it in items:
            domain = urlparse(str(it["url"]).strip()).hostname or ""
            src = await src_repo.get_or_create(domain=domain, name=domain)
            art = Article(
                source_id=src.id,
                url=str(it["url"]),
                title=str(it.get("title") or ""),
                author=None,
                content_text=str(it.get("content") or it.get("description") or ""),
                content_html=None,
                lang="vi",
                category=None,
                tags=None,
                image_url=(str(it.get("image_url")) if it.get("image_url") else None),
                published_at=None,
                metadata_=it.get("metadata") or {},
            )
            articles_to_store.append(art)

        stored_articles = await art_repo.upsert_many(articles_to_store)

        # Map back to suggestions by URL
        by_url = {a.url: a for a in stored_articles}
        for idx, it in enumerate(items, start=1):
            a = by_url.get(str(it["url"]))
            if not a:
                continue
            suggestions_to_store.append(
                DailySuggestion(
                    article_id=a.id,
                    suggestion_date=target_day,
                    rank=idx,
                    # Fallback to the full content for reason
                    reason=str(it.get("content") or it.get("description") or ""),
                )
            )

        await sug_repo.upsert_many(suggestions_to_store)
        await session.commit()

    return items
