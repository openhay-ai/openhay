from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from urllib.parse import urlparse

from backend.core.models import Article, DailySuggestion
from backend.core.repositories import (
    ArticleRepository,
    ArticleSourceRepository,
    DailySuggestionRepository,
)
from backend.core.services.web_discovery import WebDiscovery
from backend.db import AsyncSessionLocal
from backend.settings import settings
from fastapi import APIRouter, BackgroundTasks
from loguru import logger
from pydantic import BaseModel, Field, HttpUrl
from pydantic_ai import Agent
from sqlalchemy import text

router = APIRouter(prefix="/api/featured", tags=["featured"])


class BaseFeaturedItem(BaseModel):
    title: str = Field(description=("Title of the article, keep it short, within 10 words."))
    summary: str
    source: str = Field(description="domain, e.g. vnexpress.net")


class FeaturedItem(BaseFeaturedItem):
    url: HttpUrl
    published_at: Optional[datetime] = None
    image_url: Optional[HttpUrl] = Field(
        description="From the content, select the image URL that you think is most relevant."
    )


class LlmFeaturedItem(BaseFeaturedItem):
    index: int = Field(description="Index of the article in the list. Starts from 0.")


# Agent to extract top articles from crawled pages
news_agent = Agent(
    settings.model,
    output_type=list[LlmFeaturedItem],
    system_prompt=(
        "You are a news curator for Vietnam.\n"
        "Given a list of crawled pages (title, site, url, content), "
        "pick the TOP 10 most important news in Vietnam for a given day.\n"
        "Prefer breaking news, politics, economy, social, technology.\n"
        "Return JSON list with: index (important), title"
        "1-2 sentence summary, source domain,"
        "image URL, and optional published_at (ISO)."
    ),
)


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
                            logger.info(f"Acquired lock, generating featured for {today}")
                            try:
                                await generate_today_featured(today)
                            finally:
                                await conn.execute(
                                    text("SELECT pg_advisory_unlock(hashtext(:k)::bigint)"),
                                    {"k": lock_key},
                                )
                            use_suggestions = await sug_repo.list_for_day(today)
                            cnt = len(use_suggestions)
                            logger.info(f"Returning {cnt} items for {today}")
                        else:
                            logger.info(
                                f"Worker generating for {today} waiting...",
                            )

                            # Fallback to yesterday if not ready in time
                            yesterday_featured = await sug_repo.list_for_day(last_day)
                            cnt = len(yesterday_featured)
                            logger.info(f"Timeout; returning {cnt} items for {last_day}")
                            use_suggestions = yesterday_featured
            else:
                # Before cutoff, do not generate yet; use yesterday's
                yesterday_featured = await sug_repo.list_for_day(last_day)
                cnt = len(yesterday_featured)
                msg = f"Returning {cnt} featured items for {last_day} (before cutoff)"
                logger.info(msg)
                use_suggestions = yesterday_featured

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
                    "summary": s.reason or a.content_text[:200],
                    "source": urlparse(a.url).hostname or "",
                    "published_at": (a.published_at.isoformat() if a.published_at else None),
                }
            )

        return {"items": items}


async def generate_today_featured(target_day: date) -> list[FeaturedItem]:
    # Crawl from VN famous sites via Brave + crawler
    # use Vietnamese query with date
    q = (
        "Tin tức Việt Nam ngày "
        f"{target_day.strftime('%d/%m/%Y')} "
        "site:vnexpress.net OR site:tuoitre.vn OR site:thanhnien.vn "
        "OR site:plo.vn OR site:laodong.vn"
    )
    results = await WebDiscovery().discover(q, count=20)

    docs: list[dict] = []
    for idx, r in enumerate(results):
        docs.append(
            {
                "index": idx,
                "title": r.title,
                "url": r.url,
                "image_url": r.image_url,
                "content": r.content or r.description,
            }
        )

    # Ask the agent to select top 10
    formatted_prompt = (
        "Pick the top 10 most important news in Vietnam for a given day.\n"
        "Return in the correct JSON format.\n"
        f"Today: {target_day.isoformat()}\n"
        f"Data: {docs!r}"
    )
    result = await news_agent.run(formatted_prompt)
    selected_items: list[LlmFeaturedItem] = list(result.output)[:10]

    items: list[FeaturedItem] = []
    for doc in docs:
        for si in selected_items:
            if si.index == doc.get("index"):
                # Extract the summary and title from LLM
                # But every other fields are kept as original
                doc["summary"] = si.summary
                doc["title"] = si.title
                doc["source"] = si.source
                del doc["index"]
                items.append(FeaturedItem.model_validate(doc))

    # Persist
    async with AsyncSessionLocal() as session:
        src_repo = ArticleSourceRepository(session)
        art_repo = ArticleRepository(session)
        sug_repo = DailySuggestionRepository(session)

        articles_to_store: list[Article] = []
        suggestions_to_store: list[DailySuggestion] = []

        for idx, it in enumerate(items):
            domain = urlparse(str(it.url)).hostname or ""
            src = await src_repo.get_or_create(domain=domain, name=domain)
            art = Article(
                source_id=src.id,
                url=str(it.url),
                title=it.title,
                author=None,
                content_text=it.summary,
                content_html=None,
                lang="vi",
                category=None,
                tags=None,
                image_url=str(it.image_url) if it.image_url else None,
                published_at=it.published_at,
            )
            articles_to_store.append(art)

        stored_articles = await art_repo.upsert_many(articles_to_store)

        # Map back to suggestions by URL
        by_url = {a.url: a for a in stored_articles}
        for idx, it in enumerate(items, start=1):
            a = by_url.get(str(it.url))
            if not a:
                continue
            suggestions_to_store.append(
                DailySuggestion(
                    article_id=a.id,
                    suggestion_date=target_day,
                    rank=idx,
                    reason=it.summary,
                )
            )

        await sug_repo.upsert_many(suggestions_to_store)
        await session.commit()

    return items
