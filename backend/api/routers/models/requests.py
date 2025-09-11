from __future__ import annotations

from pydantic import Field

from backend.core.mixins import ConversationMixin
from backend.core.services.base import BinaryContentIn


class BaseTranslateRequest(ConversationMixin):
    target_lang: str = "Vietnamese"
    source_lang: str = "English"
    message: str = ""


class TranslateURLRequest(BaseTranslateRequest):
    url: str


class TranslateFileRequest(BaseTranslateRequest):
    media: list[BinaryContentIn] = Field(default_factory=list)
