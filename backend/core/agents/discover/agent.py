import json
from typing import Optional

import logfire
from backend.core.agents.discover.prompts import discover_system_prompt
from backend.core.services.llm_invoker import llm_invoker
from backend.core.services.web_discovery import CrawlResult, WebDiscovery
from backend.settings import settings
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter
from pydantic import BaseModel, Field
from pydantic_ai import Agent

logfire.configure(token=settings.logfire_token, scrubbing=False, environment=settings.env)
logfire.instrument_pydantic_ai()


class SelectedArticle(BaseModel):
    index: int
    title: str = Field(
        description=("Title of the article, keep it short, within 10 words. MUST BE in Vietnamese.")
    )


class SelectionResult(BaseModel):
    selected_articles: list[SelectedArticle]


@logfire.instrument("discover.deep_crawl")
async def deep_crawl(
    url: str,
    max_depth: int = 3,
    max_pages: int = 50,
    patterns: Optional[list[str]] = None,
):
    svc = WebDiscovery(max_concurrency=5)

    if patterns:
        filter_chain = FilterChain(
            filters=[
                URLPatternFilter(patterns=patterns),
            ],
        )
    else:
        filter_chain = FilterChain()

    deep_crawl_strategy = BFSDeepCrawlStrategy(
        max_depth=max_depth,
        include_external=False,
        max_pages=max_pages,
        filter_chain=filter_chain,
    )

    results = await svc.crawl_one(
        url, pruned=False, deep=True, deep_crawl_strategy=deep_crawl_strategy
    )

    return results


def _truncate(text: str | None, max_chars: int = 4000) -> str:
    if not text:
        return ""
    t = text.strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 3] + "..."


@logfire.instrument("discover._select_for_source")
async def _select_for_source(
    *,
    source_cfg: dict,
    crawled: list[CrawlResult],
) -> list[CrawlResult]:
    # Build compact post list with indices for the LLM
    posts_payload: list[dict] = []
    for idx, item in enumerate(crawled):
        posts_payload.append(
            {
                "index": idx,
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "content": _truncate(
                    item.get("content", ""),
                    3000,
                ),
            }
        )

    target_prompt = source_cfg.get(
        "target_prompt",
        ("Select the most relevant, high-quality articles for this source."),
    )
    prompt = discover_system_prompt.format(
        target_prompt=target_prompt,
        posts=json.dumps(
            posts_payload,
            ensure_ascii=False,
            indent=2,
        ),
    )

    # Create a lightweight agent for structured selection
    agent = Agent(
        settings.discover_model,
        output_type=SelectionResult,
        retries=3,
        name="discover_agent",
    )

    result = await llm_invoker.run(lambda: agent.run(prompt))
    selection: SelectionResult = result.output  # type: ignore[assignment]

    # Map back to crawled results using indices, override title with AI title
    selected: list[CrawlResult] = []
    seen_indices: set[int] = set()
    cfg_category = (source_cfg.get("category") or "").strip()
    for sel in selection.selected_articles:
        if sel.index in seen_indices:
            continue
        if sel.index < 0 or sel.index >= len(crawled):
            continue
        original = dict(crawled[sel.index])  # copy TypedDict -> dict
        original["title"] = sel.title
        meta = original.get("metadata") or {}
        try:
            meta = dict(meta)
        except Exception:
            meta = {"_raw_metadata": str(meta)}
        meta["source_config_url"] = source_cfg.get("url", "")
        if cfg_category:
            original["category"] = cfg_category
        original["metadata"] = meta
        selected.append(original)  # type: ignore[arg-type]
        seen_indices.add(sel.index)

    return selected


@logfire.instrument("discover.discover_best_posts")
async def discover_best_posts() -> list[CrawlResult]:
    """Crawl configured sources and select the best posts per source.

    Returns:
        A flat list of selected posts (per CrawlResult schema) with titles
        replaced by AI-generated short Vietnamese titles.
    """
    cfg_list = settings.discover_sources_config
    if not cfg_list:
        return []

    # Crawl and select sequentially per source (no parallelization)
    final: list[CrawlResult] = []
    for cfg in cfg_list:
        if not isinstance(cfg, dict) or not cfg.get("url"):
            continue
        url = cfg.get("url", "")
        max_depth = int(cfg.get("max_depth", 1))
        max_pages = int(cfg.get("max_pages", 50))
        patterns = cfg.get("patterns") or []
        crawled = await deep_crawl(
            url,
            max_depth=max_depth,
            max_pages=max_pages,
            patterns=patterns,
        )  # type: ignore[arg-type]
        if not crawled:
            continue
        selected = await _select_for_source(
            source_cfg=cfg,
            crawled=crawled,
        )
        final.extend(selected)

    return final


__all__ = [
    "deep_crawl",
    "discover_best_posts",
]
