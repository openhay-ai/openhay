import logfire
from backend.core.services.web_discovery import SearchResult, WebDiscovery


@logfire.instrument("search")
async def search(query: str, count: int = 5) -> list[SearchResult]:
    """Compatibility wrapper that delegates to `WebDiscovery` singleton."""
    svc = WebDiscovery()
    return await svc.discover(query=query, count=count)


@logfire.instrument("fetch_url")
async def fetch_url(urls: list[str]) -> list[dict]:
    """Fetch content directly from a list of URLs.

    Args:
        urls: List of URLs to fetch content from.

    Returns:
        List of dictionaries, each containing the URL, content (markdown), and image_url if found.
    """
    svc = WebDiscovery()
    results = await svc.crawl(urls)
    return results


if __name__ == "__main__":
    import asyncio

    res = asyncio.run(search("Tin tức mới nhất về tổng bí thư Tô Lâm"))
    if res:
        print(res[0].title)

    res_url = asyncio.run(
        fetch_url(
            [
                "https://vnexpress.net/tong-bi-thu-thu-tuong-cat-bang-khanh-thanh-khoi-cong-250-cong-trinh-4928547.html"
            ]
        )
    )
    print(res_url)
    if res_url:
        print(res_url[0].get("url"))
