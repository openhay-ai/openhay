import asyncio

from backend.core.agents.research.deps import ResearchDeps
from backend.core.agents.research.prompts import (
    lead_agent_system_prompt,
    subagent_system_prompt,
)
from backend.core.services.llm_invoker import llm_invoker
from backend.core.services.web_discovery import WebDiscovery
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
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


async def web_fetch(urls: list[str], timeout: int = 30) -> list[dict]:
    """Retrieve the complete content of a webpage.

    This tool fetches the full content of webpages and should be used to get
    detailed information after identifying promising sources through
    web_search. It's essential for thorough research as search snippets
    often lack sufficient detail.

    Args:
        urls (list[str]): The complete URLs of the webpages to fetch. Must be
            valid HTTP/HTTPS URLs.
        timeout (int, optional): Request timeout in seconds. Defaults to 30.

    Note:
        - Always use this after web_search to get complete information
        - Required when user provides a URL directly
        - Essential for getting detailed info beyond search snippets
        - Use for high-quality sources identified through web_search
    """
    svc = WebDiscovery()
    crawled = await svc.crawl(urls=urls, timeout=timeout)
    return crawled


async def complete_task(report: str) -> str:
    """Complete the research task and submit final report to lead researcher.

    Args:
        report (str): The final research report with findings and analysis
    """
    # Return the report so callers can extract it from tool results if needed
    return report


base_toolset = FunctionToolset(tools=[web_search, web_fetch])


subagent_model = GoogleModel("gemini-2.5-flash")
subagent_settings = GoogleModelSettings(
    google_thinking_config={
        "thinking_budget": 2048,
        "include_thoughts": True,
    }
)
subagent = Agent(
    subagent_model,
    model_settings=subagent_settings,
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


lead_research_model = GoogleModel("gemini-2.5-pro")
lead_research_settings = GoogleModelSettings(
    google_thinking_config={
        "thinking_budget": 8096,
        "include_thoughts": True,
    }
)
lead_research_agent = Agent(
    lead_research_model,
    model_settings=lead_research_settings,
    # Do not attach function tools here; we'll provide deferred tools
    # at runtime in the router
    output_type=str,
    name="lead_research_agent",
)


@lead_research_agent.instructions
async def lead_research_agent_instructions(
    ctx: RunContext[ResearchDeps],
) -> str:
    return lead_agent_system_prompt.format(
        current_datetime=ctx.deps.current_datetime,
    )
