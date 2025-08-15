from __future__ import annotations

import asyncio
import re
from typing import Iterable, Optional
from urllib.parse import urljoin

import logfire
from aiohttp import ClientSession
from backend.settings import settings
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from pydantic import BaseModel


class SearchResult(BaseModel):
    """Web search result enriched by optional crawling.

    Fields `content` and `image_url` are filled during crawling.
    """

    id: Optional[int] = None
    title: str
    url: str
    description: str
    page_age: Optional[str] = None
    profile: dict
    language: str
    family_friendly: bool
    type: str
    subtype: str
    is_live: bool
    deep_results: Optional[dict] = None
    meta_url: dict
    age: Optional[str] = None
    # Filled during crawling phase
    content: Optional[str] = None
    image_url: Optional[str] = None


class WebDiscovery:
    """Singleton service for web discovery (search + crawl).

    - Reuses a single crawler per batch
    - Limits concurrency with a semaphore
    """

    _instance: Optional["WebDiscovery"] = None

    def __init__(self, max_concurrency: int = 8) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def __new__(cls, *args, **kwargs) -> "WebDiscovery":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def fetch_search_results(self, query: str, count: int = 5) -> list[SearchResult]:
        """Return raw Brave search results without crawling.

        Args:
            query: Search query string.
            count: Max number of results to fetch.
        """
        if not settings.brave_api_key:
            raise ValueError("Brave API key is not set")

        query = query.strip()

        async with ClientSession() as session:
            async with session.get(
                settings.brave_search_url,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "x-subscription-token": settings.brave_api_key,
                },
                params={"q": query, "count": count},
            ) as response:
                payload = await response.json()

        web_results = payload.get("web", {}).get("results", [])
        if not web_results:
            return []

        return [SearchResult.model_validate(result) for result in web_results]

    async def crawl(self, results: Iterable[SearchResult], query: str) -> list[SearchResult]:
        """Crawl each result URL and attach markdown and image.

        Args:
            results: Items to enrich in place.
            query: Optional query context for the crawler.
        """
        md_generator = DefaultMarkdownGenerator(
            options={
                "ignore_links": True,
                "ignore_images": False,
                "escape_html": False,
            }
        )
        config = CrawlerRunConfig(
            markdown_generator=md_generator,
            exclude_external_links=True,
            exclude_internal_links=True,
            exclude_social_media_links=True,
        )

        def _is_probable_icon_or_logo(text_or_url: str) -> bool:
            value = text_or_url.lower()
            bad_tokens = [
                "icon",
                "favicon",
                "apple-touch-icon",
                "logo",
                "sprite",
                "brand",
                "placeholder",
                "avatar",
                "badge",
            ]
            if any(token in value for token in bad_tokens):
                return True

            bad_exts = [".svg", ".ico", ".gif"]
            if any(value.endswith(ext) for ext in bad_exts):
                return True

            return False

        def _extract_first_image_url(markdown: str, base_url: str) -> Optional[str]:
            # Pattern for Markdown images: ![alt](url)
            pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
            for match in re.finditer(pattern, markdown):
                alt_text = match.group(1).strip() if match.group(1) else ""
                raw_url = match.group(2).strip()
                if not raw_url or raw_url.startswith("data:"):
                    continue
                if _is_probable_icon_or_logo(alt_text):
                    continue
                if _is_probable_icon_or_logo(raw_url):
                    continue
                candidate = urljoin(base_url, raw_url)
                if _is_probable_icon_or_logo(candidate):
                    continue
                return candidate
            return None

        async with AsyncWebCrawler() as crawler:

            async def _crawl_one(item: SearchResult) -> SearchResult:
                async with self._semaphore:
                    crawl_result = await crawler.arun(
                        url=item.url,
                        query=query,
                        config=config,
                    )
                    if crawl_result.success:
                        item.content = str(crawl_result.markdown)
                        img = _extract_first_image_url(item.content, item.url)
                        item.image_url = img or item.image_url
                    else:
                        logfire.info("Crawl failed", url=item.url)
                return item

            return await asyncio.gather(*[_crawl_one(r) for r in results])

    @logfire.instrument("web_discovery.discover")
    async def discover(self, query: str, count: int = 5) -> list[SearchResult]:
        """Search the web, then crawl results to enrich content.

        Args:
            query: Search query string.
            count: Max number of results to return.
        """
        base = await self.fetch_search_results(query=query, count=count)
        if not base:
            return []
        enriched = await self.crawl(base, query=query)
        return enriched


__all__ = ["SearchResult", "WebDiscovery"]
