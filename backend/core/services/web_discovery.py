from __future__ import annotations

import asyncio
from time import monotonic
from typing import Iterable, Optional, TypedDict

import logfire
from aiohttp import ClientSession
from backend.settings import settings
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, DeepCrawlStrategy
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


class CrawlResult(TypedDict):
    url: str
    title: str
    description: str
    content: str
    image_url: str
    metadata: dict
    category: Optional[str]


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

    @logfire.instrument("web_discovery.fetch_search_results")
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

    async def crawl_one(
        self,
        url: str,
        ignore_links: bool = True,
        ignore_images: bool = False,
        escape_html: bool = False,
        pruned: bool = True,
        deep: bool = False,
        deep_crawl_strategy: DeepCrawlStrategy = BFSDeepCrawlStrategy(
            max_depth=1, include_external=False, max_pages=100
        ),
        crawler: Optional[AsyncWebCrawler] = None,
    ) -> list[CrawlResult]:
        # Build pruning filter per call
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
            deep_crawl_strategy=deep_crawl_strategy if deep else None,
        )

        async def _run_with_crawler(
            active_crawler: AsyncWebCrawler,
        ) -> list[CrawlResult]:
            async with self._semaphore:
                crawl_result = await active_crawler.arun(
                    url=url,
                    config=config,
                )
                # Normalize to a list of underlying results when deep crawl
                underlying_results = (
                    crawl_result if isinstance(crawl_result, list) else [crawl_result]
                )

                normalized: list[CrawlResult] = []
                for r in underlying_results:
                    if getattr(r, "success", False):
                        raw_markdown = str(r.markdown.raw_markdown)
                        fit_markdown = str(r.markdown.fit_markdown)
                        content = (
                            fit_markdown
                            if len(fit_markdown.replace("\n", "").strip()) > 1
                            else raw_markdown
                        )
                        metadata = getattr(r, "metadata", {}) or {}
                        image_url = (
                            metadata.get(
                                "og:image",
                                metadata.get("twitter:image", ""),
                            )
                            or ""
                        )
                        title = (
                            metadata.get(
                                "title",
                                metadata.get(
                                    "og:title",
                                    metadata.get("twitter:title", ""),
                                ),
                            )
                            or ""
                        )
                        description = (
                            metadata.get(
                                "description",
                                metadata.get(
                                    "og:description",
                                    metadata.get("twitter:description", ""),
                                ),
                            )
                            or ""
                        )
                        page_url = getattr(r, "url", url) or url
                        logfire.info(
                            "Crawl success",
                            url=page_url,
                            title=title,
                            description=description,
                            image_url=image_url,
                            content=content,
                            fit_markdown=fit_markdown,
                            raw_markdown=raw_markdown,
                        )
                    else:
                        page_url = getattr(r, "url", url) or url
                        title = ""
                        description = ""
                        content = ""
                        image_url = ""
                        logfire.info("Crawl failed", url=page_url)

                    normalized.append(
                        CrawlResult(
                            url=page_url,
                            title=title,
                            description=description,
                            content=content,
                            image_url=image_url,
                            metadata=metadata,
                        )
                    )

            return normalized

        if crawler is None:
            async with AsyncWebCrawler() as own_crawler:
                return await _run_with_crawler(own_crawler)
        return await _run_with_crawler(crawler)

    @logfire.instrument("web_discovery.crawl")
    async def crawl(
        self,
        urls: Iterable[str],
        ignore_links: bool = True,
        ignore_images: bool = False,
        escape_html: bool = False,
        pruned: bool = True,
        deep: bool = False,
        deep_crawl_strategy: DeepCrawlStrategy = BFSDeepCrawlStrategy(
            max_depth=1, include_external=False, max_pages=100
        ),
    ) -> list[CrawlResult]:
        """Crawl a list of URLs and extract markdown and a preview image.

        Applies the same configuration to all URLs. Internally delegates
        each URL to ``crawl_one`` and reuses a single crawler for efficiency.

        Args:
            urls: Iterable of absolute URLs to crawl.
            ignore_links: Whether to omit links in generated markdown.
            ignore_images: Whether to omit images in generated markdown.
            escape_html: Whether to escape HTML in generated markdown.
            pruned: Whether to enable the pruning content filter.
            deep: Whether to enable deep crawling (follow in-site links).
            deep_crawl_strategy: Strategy to use when deep crawling.

        Returns:
            List of dicts (one per URL) with keys: 'url', 'title',
            'description', 'content', and 'image_url'.
        """
        async with AsyncWebCrawler() as crawler:
            tasks = [
                self.crawl_one(
                    url=u,
                    ignore_links=ignore_links,
                    ignore_images=ignore_images,
                    escape_html=escape_html,
                    pruned=pruned,
                    deep=deep,
                    deep_crawl_strategy=deep_crawl_strategy,
                    crawler=crawler,
                )
                for u in urls
            ]
            per_url_lists = await asyncio.gather(*tasks)
            # Flatten list[list[CrawlResult]] -> list[CrawlResult]
            flattened: list[CrawlResult] = [item for sublist in per_url_lists for item in sublist]
            return flattened

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
