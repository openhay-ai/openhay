from __future__ import annotations

import re
from typing import List

from backend.core.agents.research.deps import ResearchDeps
from backend.settings import settings
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext


class CitationItem(BaseModel):
    n: int = Field(description="Numeric citation marker number")
    title: str = Field(description="Title of the source URL")
    url: str = Field(description="Source URL associated with the marker")


class CitationResult(BaseModel):
    citations: List[CitationItem] = Field(
        default_factory=list,
        description="Ordered bibliography mapping n -> url",
    )
    annotated_report: str = Field(description="Report with inline [n] markers inserted")


citation_agent = Agent(
    settings.subagent_research_model,
    output_type=CitationResult,
    name="citation_agent",
    retries=2,
)


@citation_agent.instructions
async def citation_agent_instructions(ctx: RunContext[ResearchDeps]) -> str:
    # Keep this prompt minimal and aligned with MVP requirements.
    return (
        "You add numeric citations to a research report.\n"
        "Rules:\n"
        "- Only insert inline numeric markers like [1], [2], ...\n"
        "- Reuse the same number for repeated references to the same URL "
        "(first-use order).\n"
        "- Do not change the report text except inserting [n] markers where "
        "appropriate.\n"
        "- Choose sentence vs paragraph granularity as you see fit.\n"
        "- Only cite from the allowed URL list provided.\n"
        "- For each citation, include title (short, human-readable page title).\n"
        "- Return JSON with fields: annotated_report (string) and citations "
        "(array of {n, title, url}).\n"
    )


def extract_urls_from_text(text: str) -> list[str]:
    """Extract URLs from markdown or plain text."""
    urls: list[str] = []
    # Markdown links: [label](url)
    for m in re.findall(r"\]\((https?://[^\s)]+)\)", text):
        urls.append(m)
    # Bare URLs
    for m in re.findall(r"(https?://[^\s)\]]+)", text):
        urls.append(m)
    # Keep order of first occurrence, deduplicate
    seen = set()
    deduped: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


__all__ = [
    "CitationItem",
    "CitationResult",
    "citation_agent",
    "extract_urls_from_text",
]
