import logfire
from backend.core.services.web_discovery import SearchResult, WebDiscovery


@logfire.instrument("search")
async def search(query: str, count: int = 5) -> list[SearchResult]:
    """Compatibility wrapper that delegates to `WebDiscovery` singleton."""
    svc = WebDiscovery()
    return await svc.discover(query=query, count=count)


if __name__ == "__main__":
    import asyncio

    res = asyncio.run(search("Tin tức mới nhất về tổng bí thư Tô Lâm"))
    if res:
        print(res[0].title)
