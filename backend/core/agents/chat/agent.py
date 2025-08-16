import logfire
from backend.core.agents.chat.deps import ChatDeps
from backend.core.agents.chat.prompts import system_prompt
from backend.core.tools.search import search
from backend.settings import settings
from loguru import logger
from pydantic_ai import Agent, RunContext

logfire.configure(token=settings.logfire_write_token, scrubbing=False)
logfire.instrument_pydantic_ai()

# TODO: Improve the citation method to reduce the token usage.


chat_agent = Agent(
    settings.model_name,
    deps_type=ChatDeps,
    output_type=str,
)


@chat_agent.instructions
async def chat_agent_instructions(ctx: RunContext[ChatDeps]) -> str:
    return system_prompt.format(
        current_datetime=ctx.deps.current_datetime,
        today_date=ctx.deps.today_date,
    )


@chat_agent.tool_plain(
    docstring_format="google",
    require_parameter_descriptions=True,
    retries=2,
)
async def search_web(query: str, n: int) -> list:
    """Search the web for recent or breaking information

    Args:
        query: A search-ready query that emphasizes recency/newness or
            website URL. For example, include terms like "tin tức",
            "mới nhất", dates, or time ranges. If the user asks
            "Tại sao bà Kim bị bắt", use "Tin tức về bà Kim bị bắt" or
            "Vì sao bà Kim bị bắt mới nhất".
        n: Number of results to return. Increase this for complex topics.
    """
    logger.debug(f'Searching web for "{query}" with {n} results')
    results = await search(query, n)
    return [w.model_dump() for w in results]


if __name__ == "__main__":
    import asyncio

    response = asyncio.run(
        chat_agent.run(
            "Tường tận chi tiết về tiểu sử của đồng chí Tô Lâm",
            deps=ChatDeps(),
        )
    )

    print(response.all_messages())
