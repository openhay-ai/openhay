from typing import Optional

from aiohttp import ClientSession
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from pydantic import BaseModel

from backend.settings import settings


class SearchResult(BaseModel):
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
    # For crawler to fill in
    content: Optional[str] = None


async def search(
    query: str,
    count: int = 5,
) -> list[SearchResult]:
    """Search the web for the given query, returns a list of search results with page content for each result."""

    # Strip the query
    query = query.strip()

    if not settings.brave_api_key:
        raise ValueError("Brave API key is not set")

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
            response = await response.json()

    web_results = response.get("web", {}).get("results", [])
    if not web_results:
        return []

    web_results = [SearchResult.model_validate(result) for result in web_results]

    md_generator = DefaultMarkdownGenerator(
        options={
            "ignore_links": True,
            "ignore_images": True,
            "escape_html": False,
        }
    )
    config = CrawlerRunConfig(
        markdown_generator=md_generator,
        exclude_external_links=True,
        exclude_internal_links=True,
        exclude_social_media_links=True,
    )

    # Use crawler to get page content for each result
    async with AsyncWebCrawler() as crawler:
        for idx, result in enumerate(web_results):
            # Also set the id for the result
            result.id = idx + 1
            crawl_result = await crawler.arun(
                url=result.url,
                query=query,
                config=config,
            )
            if crawl_result.success:
                result.content = str(crawl_result.markdown)
            else:
                print("Crawl failed for result: ", result.url)

    return web_results


if __name__ == "__main__":
    import asyncio

    crawler = AsyncWebCrawler()
    result = asyncio.run(
        search(
            "Tin tức mới nhất về tổng bí thư Tô Lâm",
        )
    )

    print(f"Final result: {result[0].content[:100]}")
