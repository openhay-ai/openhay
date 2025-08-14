from uuid import UUID

from pydantic import BaseModel
from pydantic_ai.messages import ModelRequestPart, ModelResponsePart


class ConversationHistoryResponse(BaseModel):
    conversation_id: UUID
    messages: list[ModelRequestPart | ModelResponsePart]
