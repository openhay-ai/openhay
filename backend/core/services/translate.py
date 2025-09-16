from __future__ import annotations

from typing import Optional
import io

from docx import Document
import mammoth
from markdownify import markdownify as md

from backend.core.auth import AuthUser
from backend.core.models import Conversation, FeatureKey, FeaturePreset
from backend.core.services.base import BaseConversationService, BinaryContentIn
from backend.core.tools.search import fetch_url
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select


class TranslateService(BaseConversationService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    @staticmethod
    def gemini_supported_mime_types() -> set[str]:
        """Return a conservative set of MIME types Gemini reliably supports as inline data.

        Notes:
            - Images, audio, video use type prefixes and are matched separately.
            - PDF is supported as application/pdf.
            - Plain/markdown/text formats are supported.
        """
        return {
            "application/pdf",
            "text/plain",
            "text/markdown",
            "text/html",
        }

    @staticmethod
    def is_gemini_supported_media_type(media_type: str | None) -> bool:
        if not media_type:
            return False
        mt = media_type.lower()
        if mt.startswith("image/"):
            return True
        if mt.startswith("audio/"):
            return True
        if mt.startswith("video/"):
            return True
        if mt in TranslateService.gemini_supported_mime_types():
            return True
        return False

    async def create_conversation_with_preset(
        self, *, owner: AuthUser | None = None
    ) -> Conversation:
        preset = (
            (
                await self.session.execute(
                    select(FeaturePreset).where(FeaturePreset.key == FeatureKey.dich)
                )
            )
            .scalars()
            .first()
        )
        if preset is None:
            stmt = select(FeaturePreset)
            result = await self.session.execute(stmt)
            preset = result.scalars().first()
        if preset is None:
            raise RuntimeError("No feature preset available")

        feature_params = {"user_id": owner.user_id} if owner else None
        conversation = await self.conversation_repo.create(preset, feature_params=feature_params)
        return conversation

    async def fetch_markdown_from_url(self, url: str) -> str | None:
        try:
            results = await fetch_url(
                [url],
                ignore_links=True,
                ignore_images=True,
                escape_html=True,
                pruned=True,
            )
            if not results:
                return None
            return results[0].get("content")
        except Exception:
            logger.exception("Failed to fetch URL content")
            return None

    def extract_text_from_media(self, media: Optional[list[BinaryContentIn]]) -> str:
        if not media:
            return ""
        # MVP: assume first item is the primary content; try to decode as UTF-8 text
        item = media[0]
        raw_bytes = self._b64_to_bytes(item.data)
        media_type = (item.media_type or "").lower()

        # DOCX handling: extract Markdown content
        if media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            try:
                with io.BytesIO(raw_bytes) as f:
                    # Convert DOCX -> HTML using Mammoth, then HTML -> Markdown
                    result = mammoth.convert_to_html(f)
                    html = result.value or ""
                    # Normalize HTML to Markdown, preserving headings/lists as best as possible
                    markdown = md(html, heading_style="ATX")
                    if markdown.strip():
                        return markdown
                    # Fallback to simple paragraph extraction if conversion produced nothing
                    f.seek(0)
                    doc = Document(f)
                    parts: list[str] = []
                    for para in doc.paragraphs:
                        if para.text:
                            parts.append(para.text)
                    return "\n".join(parts)
            except Exception:
                logger.exception("Failed to extract text from DOCX; falling back to utf-8 decode")

        # Fallback: best-effort UTF-8 decode
        try:
            return raw_bytes.decode("utf-8", errors="replace")
        except Exception:
            logger.exception("Failed to decode media as utf-8 text")
            return ""
