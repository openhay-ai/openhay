from pydantic_ai.messages import (
    BuiltinToolReturnPart,
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
