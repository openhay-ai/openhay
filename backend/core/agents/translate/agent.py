import logfire
from backend.core.agents.translate.deps import TranslateDeps
from backend.core.agents.translate.prompts import (
    system_prompt as translate_system_prompt,
)
from backend.settings import settings
from pydantic_ai import Agent, RunContext

logfire.configure(token=settings.logfire_token, scrubbing=False, environment=settings.env)
logfire.instrument_pydantic_ai()


translate_agent = Agent(
    settings.model,
    deps_type=TranslateDeps,
    output_type=str,
    retries=2,
)


@translate_agent.instructions
async def translate_instructions(ctx: RunContext[TranslateDeps]) -> str:
    return translate_system_prompt.format(
        target_lang=ctx.deps.target_lang,
        source_lang=ctx.deps.source_lang,
        content_to_translate=ctx.deps.content_to_translate,
    )
