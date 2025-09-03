from __future__ import annotations

import asyncio
import re
from time import monotonic
from typing import Iterable, Optional
from urllib.parse import urljoin

import logfire
from aiohttp import ClientSession
from backend.settings import settings
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from loguru import logger
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
        # Idempotent init: only set up once
        if getattr(self, "_initialized", False):
            return
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._initialized = True

    def __new__(cls, *args, **kwargs) -> "WebDiscovery":
        if cls._instance is None:
            instance = super().__new__(cls)
            # One-time fields shared for the singleton lifetime
            instance._api_lock = asyncio.Lock()
            instance._last_brave_call_ts = 0.0
            instance._n_running = 0
            instance._initialized = False
            cls._instance = instance
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

        self._n_running += 1
        logger.debug(
            "Brave API request running: {}, last call: {}",
            self._n_running,
            self._last_brave_call_ts,
        )
        try:
            await self._throttle_brave_api()
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
        finally:
            self._n_running -= 1

        web_results = payload.get("web", {}).get("results", [])
        if not web_results:
            return []

        return [SearchResult.model_validate(result) for result in web_results]

    async def _throttle_brave_api(self) -> None:
        """Ensure at most one Brave API request per second.

        Uses a shared lock and the last-call timestamp so that concurrent
        callers queue and respect the minimum interval across the process.
        """
        async with self._api_lock:
            now = monotonic()
            min_interval_seconds = 1.1
            elapsed = now - self._last_brave_call_ts
            if elapsed < min_interval_seconds:
                wait_s = min_interval_seconds - elapsed
                logger.debug("Brave API throttling: wait {:.2f}s", wait_s)
                await asyncio.sleep(wait_s)
            # Update after any required wait to mark the time of this call
            self._last_brave_call_ts = monotonic()

    @logfire.instrument("web_discovery.crawl")
    async def crawl(
        self,
        urls: Iterable[str],
        timeout: int = 30,
        ignore_links: bool = True,
        ignore_images: bool = False,
        escape_html: bool = False,
        pruned: bool = True,
    ) -> list[dict]:
        """Crawl each URL and return extracted markdown + first image.

        Args:
            urls: List/iterable of URLs to crawl.
            timeout: Per-request timeout (seconds). Not used directly.
            ignore_links: Whether to ignore links.
            ignore_images: Whether to ignore images.
            escape_html: Whether to escape HTML.
            pruned: Whether to prune the content.
        Returns:
            A list of dicts with shape: {"url", "content", "image_url"}
        """
        # Step 1: Create a pruning filter
        if pruned:
            logger.debug("Use pruning filter")
            prune_filter = PruningContentFilter(
                threshold=1.0,
                threshold_type="fixed",
                min_word_threshold=10,
            )
        else:
            logger.debug("Don't use pruning filter")
            prune_filter = None

        md_generator = DefaultMarkdownGenerator(
            options={
                "ignore_links": ignore_links,
                "ignore_images": ignore_images,
                "escape_html": escape_html,
            },
            content_filter=prune_filter,
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

        def _extract_first_image_url(
            markdown: str,
            base_url: str,
        ) -> Optional[str]:
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

            async def _crawl_one(url: str) -> dict:
                async with self._semaphore:
                    crawl_result = await crawler.arun(
                        url=url,
                        config=config,
                    )
                    content: Optional[str] = None
                    image_url: Optional[str] = None
                    if crawl_result.success:
                        raw_markdown = str(crawl_result.markdown.raw_markdown)
                        fit_markdown = str(crawl_result.markdown.fit_markdown)
                        content = (
                            fit_markdown
                            if len(fit_markdown.replace("\n", "").strip()) > 1
                            else raw_markdown
                        )
                        image_url = _extract_first_image_url(content, url)
                        logfire.info(
                            "Crawl success",
                            url=url,
                            image_url=image_url,
                            content=content,
                            fit_markdown=fit_markdown,
                            raw_markdown=raw_markdown,
                        )
                    else:
                        logfire.info("Crawl failed", url=url)
                return {"url": url, "content": content, "image_url": image_url}

            return await asyncio.gather(*[_crawl_one(u) for u in urls])

    @logfire.instrument("web_discovery.discover")
    async def discover(
        self,
        query: str,
        count: int = 5,
        pruned: bool = True,
        ignore_links: bool = True,
        ignore_images: bool = False,
        escape_html: bool = False,
    ) -> list[SearchResult]:
        """Search the web, then crawl results to enrich content.

        Args:
            query: Search query string.
            count: Max number of results to return.
        """
        raw_results = await self.fetch_search_results(query=query, count=count)
        if not raw_results:
            return []
        # Build SearchResult models
        results = [SearchResult.model_validate(r) for r in raw_results]
        # Crawl URLs and merge content into results by URL
        url_list = [r.url for r in results]
        crawled = await self.crawl(
            url_list,
            pruned=pruned,
            ignore_links=ignore_links,
            ignore_images=ignore_images,
            escape_html=escape_html,
        )
        data_by_url = {item.get("url"): item for item in crawled}
        for r in results:
            data = data_by_url.get(r.url) or {}
            r.content = data.get("content")
            r.image_url = data.get("image_url") or r.image_url
        return results


__all__ = ["SearchResult", "WebDiscovery"]
