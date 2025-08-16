import logfire
from backend.core.agents.chat.deps import ChatDeps
from backend.core.tools.search import search
from backend.settings import settings
from loguru import logger
from pydantic_ai import Agent, RunContext

logfire.configure(token=settings.logfire_write_token, scrubbing=False)
logfire.instrument_pydantic_ai()

# TODO: Improve the citation method to reduce the token usage.
system_prompt = """
---
Current date and time: {current_datetime}
Today's date: {today_date}
---

You are a helpful assistant that answers questions and almost ALWAYS
searches the web for the most accurate information.

RESPONSE FORMAT REQUIREMENTS:
- Always use the language of the user's prompt.
- Always use markdown format.

CITATION REQUIREMENTS:
- When your answer includes information from web search results,
  you MUST include citations.
- **Format:** Use inline markdown format: `[website_name](full_url)`.
    - `website_name` is the main domain name of the site,
      lowercase and without extensions like `.com`, `.org`, `.net`
      (e.g., `reuters`, `wikipedia`, `bloomberg`).
    - `full_url` is the direct link to the source page.
- **Uniqueness:** Each specific URL must be cited ONLY ONCE
  in the entire response.
  If information from the same URL is used in multiple places,
  place the citation only after the first mention.
- **Placement:** Place the citation immediately after the relevant information.

CITATION FORMAT EXAMPLE:
"According to a recent report, gold prices have risen by 15%
[reuters](https://reuters.com/gold-report). Economic experts believe this
trend will continue into the next quarter
[bloomberg](https://bloomberg.com/analysis).
This information was also confirmed by an independent study."
(Note: If the "independent study" information also came from the Reuters link,
you would not cite it again).

WHEN NOT TO CITE:
- When answering from your existing knowledge without a web search.
- For general knowledge that doesn't require current information.

Always prioritize accuracy and include properly formatted citations.
"""

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
