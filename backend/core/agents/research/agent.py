import asyncio
import json

import logfire
from backend.core.agents.research.citation import (
    CitationItem,
    CitationResult,
    citation_agent,
    extract_urls_from_text,
)
from backend.core.agents.research.deps import ResearchDeps
from backend.core.agents.research.prompts import (
    lead_agent_system_prompt,
    subagent_system_prompt,
)
from backend.core.services.llm_invoker import llm_invoker
from backend.core.services.web_discovery import WebDiscovery
from backend.settings import settings
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.toolsets import FunctionToolset


async def web_search(query: str, max_results: int = 10) -> list[dict]:
    """Search the web for information related to a query.

    This tool performs a web search and returns snippets/summaries of search
    results along with their URLs. It's designed to provide an overview of
    available sources and should be used as the first step in a research
    process to identify promising sources for further investigation.

    Args:
        query (str): The search query. Should be concise (under 5 words)
            and moderately broad rather than hyper-specific for best
            results.
        max_results (int, optional): Maximum number of search results to
            return. Defaults to 10.

    Note:
        - Use broad queries initially, then narrow if results are too general
        - Avoid repeating identical queries as this wastes resources
        - Results contain only snippets - use web_fetch for complete content
        - Can be called in parallel with other tools for efficiency
    """
    svc = WebDiscovery()
    search_results = await svc.fetch_search_results(
        query=query,
        count=max_results,
    )
    return [sr.model_dump() for sr in search_results]


async def web_fetch(urls: list[str]) -> list[dict]:
    """Retrieve the complete content of a webpage.

    This tool fetches the full content of webpages and should be used to get
    detailed information after identifying promising sources through
    web_search. It's essential for thorough research as search snippets
    often lack sufficient detail.

    Args:
        urls (list[str]): The complete URLs of the webpages to fetch. Must be
            valid HTTP/HTTPS URLs.

    Note:
        - Always use this after web_search to get complete information
        - Required when user provides a URL directly
        - Essential for getting detailed info beyond search snippets
        - Use for high-quality sources identified through web_search
    """
    svc = WebDiscovery()
    crawled = await svc.crawl(urls=urls, pruned=False, ignore_images=True)
    return crawled


async def complete_task(report: str) -> str:
    """Complete the research task and submit final report to lead researcher.

    Args:
        report (str): The final research report with findings and analysis
    """
    # Return the report so callers can extract it from tool results if needed
    return report


base_toolset = FunctionToolset(tools=[web_search, web_fetch])


subagent_model = settings.subagent_research_model
subagent = Agent(
    subagent_model,
    toolsets=[base_toolset],
    output_type=str,
    name="subagent",
    retries=3,
)


@subagent.instructions
async def subagent_instructions(ctx: RunContext[ResearchDeps]) -> str:
    return subagent_system_prompt.format(
        current_datetime=ctx.deps.current_datetime,
    )


# Lead Research Agent
lead_research_toolset = FunctionToolset(max_retries=0)


@lead_research_toolset.tool(
    docstring_format="google",
    require_parameter_descriptions=True,
    retries=0,
)
async def run_parallel_subagents(
    ctx: RunContext[ResearchDeps],
    prompts: list[str],
) -> list[str]:
    """Run multiple research subagents concurrently.

    Args:
        prompts (list[str]): A list of detailed task instructions,
            one per subagent.

    Returns:
        list[str]: Each subagent's complete research report in the same
            order as prompts.
    """

    # Limit concurrent subagent executions
    semaphore = asyncio.Semaphore(1)

    async def _one(p: str) -> str:
        async with semaphore:
            res = await llm_invoker.run(
                lambda: subagent.run(
                    p,
                    deps=ctx.deps,
                    usage=ctx.usage,
                ),
                max_attempts=3,
            )
            return res.output

    # Safety cap to avoid runaway fan-out
    if len(prompts) > 10:
        prompts = prompts[:10]

    return await asyncio.gather(*[_one(p) for p in prompts])


lead_research_model = settings.lead_research_model
lead_research_agent = Agent(
    lead_research_model,
    # Do not attach function tools here; we'll provide deferred tools
    # at runtime in the router
    output_type=str,
    name="lead_research_agent",
    retries=3,
)


@lead_research_agent.instructions
async def lead_research_agent_instructions(
    ctx: RunContext[ResearchDeps],
) -> str:
    return lead_agent_system_prompt.format(
        current_datetime=ctx.deps.current_datetime,
    )


@logfire.instrument("run_citation_phase")
async def run_citation_phase(
    report: str,
    history_text: str,
    current_citations: list[CitationItem] | None = None,
) -> CitationResult:
    """Run the citation agent to insert inline numeric markers.

    Args:
        report: The final synthesized report from the lead agent.
        history_text: Concatenated prior messages to mine allowed URLs from.

    Returns:
        CitationResult containing the annotated report and bibliography.
    """
    allowed_urls = extract_urls_from_text(history_text)
    # Provide a compact instruction payload combining the report and URLs.
    existing = current_citations or []
    existing_json = json.dumps([c.model_dump() for c in existing], ensure_ascii=False)
    prompt = (
        "You will be given a report and a list of allowed URLs.\n"
        "Insert numeric citations [n] into the report, "
        "mapping to these URLs.\n"
        "You are also given an existing citation list (JSON). Reuse numbers for\n"
        "any URL already present; only append new entries and continue numbering.\n"
        f"Allowed URLs (first-use order):\n"
        f"{chr(10).join(allowed_urls)}\n\n"
        f"Existing citations JSON:\n{existing_json}\n\n"
        f"Report:\n{report}"
    )
    result = await citation_agent.run(prompt)
    output: CitationResult = result.output
    return output


def messages_to_text(messages: list[ModelMessage], include_tools: bool = False) -> str:
    """Render a simple text view of messages for citation harvesting.

    When include_tools=True, also serialize tool calls and tool results so
    URLs inside tool payloads are available to the citation agent.
    """
    lines: list[str] = []
    for msg in messages:
        if not hasattr(msg, "parts"):
            continue
        for part in msg.parts:  # type: ignore[attr-defined]
            try:
                if isinstance(part, TextPart):
                    content = getattr(part, "content", None)
                    if isinstance(content, str):
                        lines.append(content)
                elif include_tools and isinstance(part, ToolCallPart):
                    tn = getattr(part, "tool_name", "")
                    args = getattr(part, "args", None)
                    try:
                        args_txt = (
                            json.dumps(args, ensure_ascii=False) if args is not None else "{}"
                        )
                    except Exception:
                        args_txt = str(args)
                    lines.append(f"[tool_call:{tn}] args={args_txt}")
                elif include_tools and isinstance(part, ToolReturnPart):
                    tn = getattr(part, "tool_name", "")
                    content = getattr(part, "content", None)
                    try:
                        if isinstance(content, (dict, list)):
                            c_txt = json.dumps(content, ensure_ascii=False)
                        else:
                            c_txt = str(content)
                    except Exception:
                        c_txt = str(content)
                    lines.append(f"[tool_result:{tn}] {c_txt}")
            except Exception:
                # Best-effort extraction; skip problematic parts
                continue
    return "\n".join(lines)


def filter_messages_for_citation(
    messages: list[ModelMessage],
) -> list[ModelMessage]:
    """Return a minimal message list containing only web_fetch tool results.

    Extracts each fetched page's URL and content, discarding all other tool
    calls/results and assistant/user text. The resulting list contains a single
    ModelRequest with a ToolReturnPart named "web_fetch" whose content is a
    list of {"url", "content"} items.
    """
    fetch_items: list[dict] = []
    for msg in messages:
        parts = getattr(msg, "parts", [])
        for part in parts:
            try:
                if (
                    isinstance(part, ToolReturnPart)
                    and getattr(part, "tool_name", "") == "web_fetch"
                ):
                    content = getattr(part, "content", None)
                    if isinstance(content, list):
                        for it in content:
                            if not isinstance(it, dict):
                                continue
                            url = it.get("url")
                            body = it.get("content")
                            if isinstance(url, str) and isinstance(body, str):
                                fetch_items.append({"url": url, "content": body})
            except Exception:
                continue
    if not fetch_items:
        return []
    trp = ToolReturnPart(
        tool_name="web_fetch",
        content=fetch_items,
        tool_call_id="citation_web_fetch",
    )
    return [ModelRequest(parts=[trp])]
