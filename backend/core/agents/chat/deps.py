from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ChatDeps:
    current_datetime: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
