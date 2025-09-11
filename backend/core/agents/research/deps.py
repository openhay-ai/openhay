from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class SubtaskPlan:
    """One concrete subtask derived from the lead plan.

    Fields are intentionally minimal; expand as needed.
    """

    id: str
    title: str
    objective: str
    expected_output: str
    suggested_sources: List[str] = field(default_factory=list)


@dataclass
class ResearchPlan:
    """High-level plan saved by the lead researcher into external memory."""

    user_query: str
    query_type: str  # "depth-first" | "breadth-first" | "straightforward"
    approach_summary: str
    subtasks: List[SubtaskPlan] = field(default_factory=list)

    def subplan(self, subtask_id: str) -> Optional[SubtaskPlan]:
        return next((s for s in self.subtasks if s.id == subtask_id), None)


@dataclass
class ResearchDeps:
    """Shared dependencies/state for research agents.

    - plan_id: identifier of the plan
    - plan: the detailed research plan
    - current_datetime: used in prompts
    """

    plan_id: Optional[str] = None
    plan: Optional[str] = None
    current_datetime: str = field(
        # Use local timezone and a human-readable format
        default_factory=lambda: (datetime.now().astimezone().strftime("%B %d, %Y at %I:%M %p %Z"))
    )

    def as_json(self) -> dict:
        # Minimal helper; expand if we later persist deps
        return {
            "plan_id": self.plan_id,
            "plan": self.plan,
            "current_datetime": self.current_datetime,
        }
