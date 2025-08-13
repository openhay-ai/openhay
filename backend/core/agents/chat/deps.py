from dataclasses import dataclass
from datetime import datetime

from pydantic import Field


@dataclass
class ChatDeps:
    current_datetime: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
