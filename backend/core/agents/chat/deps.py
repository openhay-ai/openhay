from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ChatDeps:
    current_datetime: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    )

    @property
    def today_date(self) -> str:
        return datetime.now(timezone.utc).date().isoformat()
