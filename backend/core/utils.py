import logfire
from pydantic_ai.messages import (
    BuiltinToolReturnPart,
    ModelMessage,
    ModelRequestPart,
    ModelResponsePart,
    RetryPromptPart,
    SystemPromptPart,
    ToolReturnPart,
    UserPromptPart,
)


def part_to_role(part: ModelRequestPart | ModelResponsePart) -> str:
    # Tool results
    if isinstance(part, (ToolReturnPart, BuiltinToolReturnPart)):
        return "tool"

    # Explicit request parts
    if isinstance(part, SystemPromptPart):
        return "system"
    if isinstance(part, UserPromptPart):
        return "user"
    if isinstance(part, RetryPromptPart):
        # Retry prompts are "user" unless they’re tied to a tool
        return "tool" if part.tool_name else "user"

    # Any other model response part
    # (text, thinking, tool-call, builtin-tool-call) is assistant
    if isinstance(part, ModelResponsePart):
        return "assistant"

    raise ValueError(f"Unknown part: {part}")


@logfire.instrument("extract_tool_return_part")
def extract_tool_return_part(
    messages: list[ModelMessage],
    tool_name: str,
) -> ToolReturnPart | None:
    for message in messages:
        for part in message.parts:
            if isinstance(part, ToolReturnPart) and part.tool_name == tool_name:
                logfire.info("Tool found", part=part)
                return part
    return None
