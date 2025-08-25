from __future__ import annotations

import json
from typing import Optional
from uuid import uuid4

import logfire
from backend.core.agents.research.agent import lead_research_agent, subagent
from backend.core.agents.research.deps import ResearchDeps
from backend.core.mixins import ConversationMixin
from backend.core.models import Conversation
from backend.core.services.chat import BinaryContentIn, ChatService
from backend.db import AsyncSessionLocal

# settings not needed here
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.messages import (
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    PartDeltaEvent,
    TextPart,
    TextPartDelta,
    ThinkingPartDelta,
    ToolReturnPart,
)
from pydantic_ai.output import DeferredToolCalls
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import DeferredToolset

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchRequest(ConversationMixin):
    query: str = Field(description="User research question")
    media: Optional[list[BinaryContentIn]] = Field(default_factory=list)
    # Optional: cap subagents for cost control
    # max_subagents: Optional[int] = Field(default=3, ge=1, le=10)


class ResearchResponse(BaseModel):
    report: str
    model: str


def _sse(event: str, data: dict) -> str:
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
                        "description": ("A list of detailed task instructions, one per subagent."),
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
        run_id = str(uuid4())
        emit_seq = 0
        conversation_created_emitted = False

        def emit(event: str, data: dict) -> str:
            nonlocal emit_seq
            emit_seq += 1
            preview_val = data.get("answer") or data.get("thinking") or data.get("results") or ""
            try:
                content_len = len(preview_val) if isinstance(preview_val, str) else -1
            except Exception:
                content_len = -1
            logger.debug(
                f"[research {run_id}] emit#{emit_seq} event={event} content_len={content_len}"
            )
            return _sse(event, data)

        async with AsyncSessionLocal() as session:
            chat_service = ChatService(session)

            # Resolve existing conversation or create a new one
            conversation: Optional[Conversation] = None
            created_new_conversation = False
            if payload.conversation_id is not None:
                conversation = await chat_service.get_conversation_by_id(payload.conversation_id)
            if conversation is None:
                create_default = chat_service.create_conversation_with_default_preset
                conversation = await create_default()
                created_new_conversation = True
            # Decode media and build user prompt like chat flow
            safe_media = chat_service.decode_media_items(payload.media)
            user_prompt = [payload.query, *safe_media]

            message_history: list[ModelMessage] = []

            while True:
                # Drive the lead agent with iter() so we can stream
                # thinking deltas

                logger.debug(f"[research {run_id}] start iteration; ")

                async with lead_research_agent.iter(
                    user_prompt,
                    message_history=message_history,
                    deps=deps,
                    toolsets=[deferred_toolset],
                    output_type=[
                        lead_research_agent.output_type,
                        DeferredToolCalls,
                    ],  # type: ignore[arg-type]
                ) as lead_run:
                    async for node in lead_run:
                        lead_thinking = ""
                        lead_answer = ""
                        logger.debug(f"[research {run_id}] node: {node}")

                        if Agent.is_model_request_node(node):
                            async with node.stream(lead_run.ctx) as req_stream:
                                logger.debug(f"[research {run_id}] open req_stream")
                                async for ev in req_stream:
                                    if isinstance(ev, PartDeltaEvent):
                                        if isinstance(ev.delta, TextPartDelta):
                                            lead_answer += ev.delta.content_delta

                                        elif isinstance(ev.delta, ThinkingPartDelta):
                                            lead_thinking += ev.delta.content_delta
                                    elif isinstance(ev, FinalResultEvent):
                                        break
                                # Emit thinking for this request
                                if lead_thinking:
                                    logger.debug(
                                        f"[research {run_id}] emit lead_thinking "
                                        f"len={len(lead_thinking)}"
                                    )
                                    yield emit(
                                        "lead_thinking",
                                        {"thinking": lead_thinking},
                                    )
                                # Only emit lead_answer if we have any text
                                if lead_answer:
                                    logger.debug(
                                        f"[research {run_id}] emit lead_answer "
                                        f"len={len(lead_answer)}"
                                    )
                                    yield emit(
                                        "lead_answer",
                                        {"answer": lead_answer},
                                    )
                                # If there was no delta text but the model
                                # responded with a final text part, emit that
                                elif hasattr(node, "model_response") and hasattr(
                                    node.model_response, "parts"
                                ):
                                    for p in node.model_response.parts:
                                        if isinstance(p, TextPart):
                                            text_content = getattr(p, "content", "")
                                            if text_content:
                                                logger.debug(
                                                    f"[research {run_id}] emit lead_answer (final text part) "
                                                    f"len={len(text_content)}"
                                                )
                                                yield emit(
                                                    "lead_answer",
                                                    {"answer": text_content},
                                                )
                                            break
                        elif Agent.is_call_tools_node(node):
                            # The model may emit assistant text alongside tool calls.
                            # Stream any text/thinking deltas from this phase too.
                            async with node.stream(lead_run.ctx) as handle_stream:
                                async for ev in handle_stream:
                                    if isinstance(ev, PartDeltaEvent):
                                        if isinstance(ev.delta, TextPartDelta):
                                            lead_answer += ev.delta.content_delta
                                        elif isinstance(ev.delta, ThinkingPartDelta):
                                            lead_thinking += ev.delta.content_delta
                            # Emit any accumulated content from this node
                            if lead_thinking:
                                logger.debug(
                                    f"[research {run_id}] emit lead_thinking (tools) "
                                    f"len={len(lead_thinking)}"
                                )
                                yield emit(
                                    "lead_thinking",
                                    {"thinking": lead_thinking},
                                )
                            if lead_answer:
                                logger.debug(
                                    f"[research {run_id}] emit lead_answer (tools) "
                                    f"len={len(lead_answer)}"
                                )
                                yield emit(
                                    "lead_answer",
                                    {"answer": lead_answer},
                                )
                            elif hasattr(node, "model_response") and hasattr(
                                node.model_response, "parts"
                            ):
                                for p in node.model_response.parts:
                                    if isinstance(p, TextPart):
                                        text_content = getattr(p, "content", "")
                                        if text_content:
                                            logger.debug(
                                                f"[research {run_id}] emit lead_answer (tools final text part) "
                                                f"len={len(text_content)}"
                                            )
                                            yield emit(
                                                "lead_answer",
                                                {"answer": text_content},
                                            )
                                        break

                    # After iteration completes, capture new messages
                    nm = lead_run.result.new_messages()
                    logfire.info("New messages", new_messages=nm)

                    # Persist only user prompt and lead agent thinking/answers
                    try:
                        msgs = ModelMessagesTypeAdapter.validate_python(nm)
                        jsonable_msgs = chat_service.to_jsonable_messages(msgs)
                        try:
                            kinds = []
                            if isinstance(jsonable_msgs, list):
                                for m in jsonable_msgs:
                                    if isinstance(m, dict):
                                        for p in m.get("parts", []):
                                            if isinstance(p, dict):
                                                k = p.get("part_kind")
                                                if k:
                                                    kinds.append(k)
                            logger.debug(
                                f"[research {run_id}] new_messages kinds={kinds} count={len(kinds)}"
                            )
                        except Exception:
                            pass

                        # Append the new messages to the message history
                        message_history.extend(msgs)

                        await chat_service.persist_message_run(
                            conversation,
                            jsonable_msgs,
                        )
                        await session.commit()

                    except Exception:
                        logger.exception("Failed to persist research lead messages run")

                    # Otherwise we expect DeferredToolCalls
                    if isinstance(lead_run.result.output, DeferredToolCalls):
                        tool_return_messages: list[ModelRequest] = []
                        for call in lead_run.result.output.tool_calls:
                            logger.debug(f"call: {call.args_as_dict()}")
                            if call.tool_name == "run_parallel_subagents":
                                args = call.args_as_dict()
                                prompts = args.get("prompts", []) or []
                                # Cap the number of subagents to 10
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
                                                            isinstance(
                                                                tev,
                                                                FunctionToolCallEvent,
                                                            )
                                                            and tev.part.tool_name == "web_search"
                                                        ):
                                                            args = tev.part.args or {}
                                                            query = (
                                                                args.get("query", "")
                                                                if isinstance(args, dict)
                                                                else ""
                                                            )
                                                            yield emit(
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
                                                            yield emit(
                                                                "web_search_results",
                                                                {
                                                                    "id": tev.result.tool_call_id,
                                                                    "index": idx,
                                                                    "results": content,
                                                                },
                                                            )
                                            elif Agent.is_end_node(sub_node):
                                                assert sub_run.result is not None
                                        results.append(
                                            sub_run.result.output if sub_run.result else ""
                                        )

                                yield emit(
                                    "subagent_completed",
                                    {},
                                )
                            # Return the concatenated reports of all subagents
                            trp = ToolReturnPart(
                                tool_name=call.tool_name,
                                content=results,
                                tool_call_id=call.tool_call_id,
                            )
                            # Append tool return to new messages
                            # to include it in persistence
                            nm.append(ModelRequest(parts=[trp]))
                            message_history.append(ModelRequest(parts=[trp]))
                            tool_return_messages.append(ModelRequest(parts=[trp]))
                        # Persist tool return messages so they are part of history
                        if tool_return_messages:
                            try:
                                jsonable_tool_msgs = chat_service.to_jsonable_messages(
                                    tool_return_messages
                                )
                                await chat_service.persist_message_run(
                                    conversation,
                                    jsonable_tool_msgs,
                                )
                                await session.commit()
                            except Exception:
                                logger.exception(
                                    ("Failed to persist research tool return messages")
                                )
                    else:
                        # Final output produced; emit final report and stop iterating
                        try:
                            final_text = (
                                lead_run.result.output
                                if isinstance(lead_run.result.output, str)
                                else ""
                            )
                            yield emit("final_report", {"report": final_text})
                        except Exception:
                            logger.exception("Failed to emit final_report event")
                        if created_new_conversation and not conversation_created_emitted:
                            evt_payload = {"conversation_id": str(conversation.id)}
                            logger.debug(f"[research {run_id}] emit conversation_created")
                            yield emit("conversation_created", evt_payload)
                            conversation_created_emitted = True
                        break

    return StreamingResponse(generator(), media_type="text/event-stream")


__all__ = ["router"]
