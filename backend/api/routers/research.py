from __future__ import annotations

from backend.core.agents.research.agent import lead_research_agent, subagent
from backend.core.agents.research.deps import ResearchDeps
from backend.settings import settings
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelRequest,
    ToolReturnPart,
)
from pydantic_ai.output import DeferredToolCalls
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import DeferredToolset

# ruff: noqa: E501


router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchRequest(BaseModel):
    query: str = Field(description="User research question")
    # Optional: cap subagents for cost control
    # max_subagents: Optional[int] = Field(default=3, ge=1, le=10)


class ResearchResponse(BaseModel):
    report: str
    model: str


def _sse(event: str, data: dict) -> str:
    import json

    payload = json.dumps(data, ensure_ascii=False)
    logger.debug(f"SSE event: {event}, data: {payload}")
    return f"event: {event}\ndata: {payload}\n\n"


@router.post(
    "",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Streaming research events",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def run_research(payload: ResearchRequest) -> StreamingResponse:
    deps = ResearchDeps()

    # Define deferred tools that the lead agent can "call"
    deferred_tools = [
        ToolDefinition(
            name="run_parallel_subagents",
            parameters_json_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "prompts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "A list of detailed task instructions, one per subagent.",
                    }
                },
                "required": ["prompts"],
            },
            description=(
                "Run multiple research subagents concurrently. "
                "Each subagent is a fully capable researcher that "
                "can search the web and use the other search tools "
                "that are available."
            ),
        ),
    ]
    deferred_toolset = DeferredToolset(deferred_tools)

    async def generator():
        message_history: list[ModelMessage] | None = None

        while True:
            run = await lead_research_agent.run(
                payload.query if message_history is None else None,
                deps=deps,
                message_history=message_history,
                toolsets=[deferred_toolset],
                output_type=[
                    lead_research_agent.output_type,
                    DeferredToolCalls,
                ],  # type: ignore[arg-type]
            )

            nm = run.all_messages()
            message_history = (message_history or []) + nm

            if isinstance(run.output, str):
                yield _sse(
                    "final_report",
                    {"report": run.output, "model": settings.model_name},
                )
                break

            assert isinstance(run.output, DeferredToolCalls)
            for call in run.output.tool_calls:
                if call.tool_name == "run_parallel_subagents":
                    args = call.args_as_dict()
                    prompts = args.get("prompts", []) or []
                    if len(prompts) > 10:
                        prompts = prompts[:10]

                    results: list[str] = []
                    for idx, p in enumerate(prompts):
                        async with subagent.iter(p, deps=deps) as sub_run:
                            async for sub_node in sub_run:
                                if Agent.is_call_tools_node(sub_node):
                                    async with sub_node.stream(sub_run.ctx) as st:
                                        async for tev in st:
                                            if (
                                                isinstance(tev, FunctionToolCallEvent)
                                                and tev.part.tool_name == "web_search"
                                            ):
                                                args = tev.part.args or {}
                                                query = (
                                                    args.get("query", "")
                                                    if isinstance(args, dict)
                                                    else ""
                                                )
                                                yield _sse(
                                                    "web_search_query",
                                                    {
                                                        "id": tev.part.tool_call_id,
                                                        "index": idx,
                                                        "query": query,
                                                    },
                                                )
                                            elif (
                                                isinstance(
                                                    tev,
                                                    FunctionToolResultEvent,
                                                )
                                                and tev.result.tool_name == "web_search"
                                            ):
                                                content = (
                                                    list(tev.result.content)
                                                    if isinstance(
                                                        tev.result.content,
                                                        list,
                                                    )
                                                    else []
                                                )
                                                yield _sse(
                                                    "web_search_results",
                                                    {
                                                        "id": tev.result.tool_call_id,
                                                        "index": idx,
                                                        "results": content,
                                                    },
                                                )
                                elif Agent.is_end_node(sub_node):
                                    assert sub_run.result is not None
                            results.append(sub_run.result.output if sub_run.result else "")

                    # Return the concatenated reports of all subagents
                    trp = ToolReturnPart(
                        tool_name=call.tool_name,
                        content=results,
                        tool_call_id=call.tool_call_id,
                    )
                    message_history.append(ModelRequest(parts=[trp]))

    return StreamingResponse(generator(), media_type="text/event-stream")


__all__ = ["router"]
