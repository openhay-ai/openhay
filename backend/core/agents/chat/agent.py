import logfire
from pydantic_ai import Agent

from backend.core.agents.chat.deps import ChatDeps
from backend.core.tools.search import search
from backend.settings import settings

logfire.configure(token=settings.logfire_write_token, scrubbing=False)
logfire.instrument_pydantic_ai()

# TODO: Improve this later to reduce the token usage for citations
system_prompt = """
You are a helpful assistant that answers questions in Vietnamese and almost ALWAYS searches the web for the most accurate information.

RESPONSE FORMAT REQUIREMENTS:
- Always use Vietnamese
- Always use markdown format

CITATION REQUIREMENTS:
- When your answer includes information from web search results, you MUST include citations
- Use inline markdown format: [descriptive text](URL) directly in the text
- Place citations immediately after the relevant information
- Use descriptive Vietnamese text for the link, not generic terms

CITATION FORMAT EXAMPLE:
"Theo báo cáo mới nhất, giá vàng đã [tăng 15%](https://vnexpress.net/gold-report). Chuyên gia kinh tế cho rằng xu hướng này sẽ tiếp tục [báo cáo của Reuters](https://reuters.com/analysis) và [phân tích từ Tuổi Trẻ](https://tuoitre.vn/economic-forecast)."

WHEN NOT TO CITE:
- When answering from your existing knowledge without web search
- For general knowledge that doesn't require current information

Always prioritize accuracy and include properly formatted inline markdown citations for any claims based on search results.
"""

chat_agent = Agent(
    settings.model_name,
    deps_type=ChatDeps,
    output_type=str,
    system_prompt=system_prompt,
)


@chat_agent.tool_plain
async def search_web(query: str, n: int = 5) -> list:
    """Use when the users need the latest news, returns a list of search results with page content for each result."""
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
