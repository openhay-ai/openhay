from __future__ import annotations


from backend.core.agents.research.agent import lead_research_agent
from backend.core.agents.research.deps import ResearchDeps
from backend.settings import settings
from fastapi import APIRouter
from pydantic import BaseModel, Field
from backend.core.services.ratelimit import run_with_quota_and_retry, gemini_flash_limiter


router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchRequest(BaseModel):
    query: str = Field(description="User research question")
    # Optional: cap subagents for cost control
    # max_subagents: Optional[int] = Field(default=3, ge=1, le=10)


class ResearchResponse(BaseModel):
    report: str
    model: str


@router.post("", response_model=ResearchResponse)
async def run_research(payload: ResearchRequest) -> ResearchResponse:
    # Seed deps with current date/time; plan memory could be wired later
    deps = ResearchDeps()

    # Execute the lead agent in a single run (no streaming) with retry/backoff on 429s
    result = await run_with_quota_and_retry(
        gemini_flash_limiter(),
        lambda: lead_research_agent.run(payload.query, deps=deps),
        max_attempts=3,
    )
    report: str = result.output or ""

    # Persisting research runs or citations can be added later
    return ResearchResponse(report=report, model=settings.model_name)


__all__ = ["router"]
