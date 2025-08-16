from uuid import UUID

from pydantic import BaseModel


class ConversationHistoryResponse(BaseModel):
    conversation_id: UUID
    # Use JSON-safe dicts to avoid bytes serialization issues
    messages: list[dict]
