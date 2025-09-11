from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ChatDeps:
    current_datetime: str = field(
        default_factory=lambda: (datetime.now().astimezone().strftime("%B %d, %Y at %I:%M %p %Z"))
    )

    @property
    def today_date(self) -> str:
        return datetime.now(timezone.utc).date().isoformat()
