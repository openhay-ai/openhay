from __future__ import annotations

from datetime import date, datetime, timedelta
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

router = APIRouter(prefix="/api/featured", tags=["featured"])


class FeaturedItem(BaseModel):
    title: str = Field(description="Title of the article, keep it short, within 10 words.")
    url: HttpUrl
    image_url: Optional[HttpUrl] = None
    summary: str
    source: str = Field(description="domain, e.g. vnexpress.net")
    published_at: Optional[datetime] = None


# Agent to extract top articles from crawled pages
news_agent = Agent(
    settings.model_name,
    output_type=list[FeaturedItem],
    system_prompt=(
        "You are a news curator for Vietnam.\n"
        "Given a list of crawled pages (title, site, url, content), "
        "pick the TOP 10 most important news in Vietnam for a given day.\n"
        "Prefer breaking news, politics, economy, social, technology.\n"
        "Return JSON list with: title, url, optional image_url, "
        "1-2 sentence summary, source domain, and optional published_at (ISO)."
    ),
)


@router.get("")
async def get_today_featured(
    background_tasks: BackgroundTasks,
) -> dict[str, list[dict]]:
    # Use local time to avoid timezone issues
    now = datetime.now()
    today = now.date()
    yesterday = today - timedelta(days=1)

    async with AsyncSessionLocal() as session:
        sug_repo = DailySuggestionRepository(session)
        art_repo = ArticleRepository(session)

        existing_today = await sug_repo.list_for_day(today)

        # Decide which day to use for response and
        # whether to kick off background generation
        if existing_today:
            cnt = len(existing_today)
            msg = f"Found {cnt} existing featured items for {today}"
            logger.info(msg)
            use_day = today
            use_suggestions = existing_today
        else:
            # After 6am local time, start generating today's featured
            cutoff = now.replace(hour=6, minute=0, second=0, microsecond=0)
            if now >= cutoff:
                background_tasks.add_task(generate_today_featured, today)

            # Always return yesterday's featured if today's is not ready
            yesterday_featured = await sug_repo.list_for_day(yesterday)
            cnt = len(yesterday_featured)
            msg = f"Returning {cnt} featured items for {yesterday}"
            logger.info(msg)
            use_day = yesterday
            use_suggestions = yesterday_featured

        # Join with articles for the selected day
        articles = await art_repo.list_by_day(use_day)
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
    for r in results:
        docs.append(
            {
                "title": r.title,
                "site": (r.meta_url.get("hostname") if r.meta_url else urlparse(r.url).hostname),
                "url": r.url,
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
    items: list[FeaturedItem] = list(result.output)[:10]

    # Persist
    async with AsyncSessionLocal() as session:
        src_repo = ArticleSourceRepository(session)
        art_repo = ArticleRepository(session)
        sug_repo = DailySuggestionRepository(session)

        articles_to_store: list[Article] = []
        suggestions_to_store: list[DailySuggestion] = []

        for idx, it in enumerate(items, start=1):
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
