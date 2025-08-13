from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Column, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TEXT
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, relationship
from sqlmodel import Field, Relationship, SQLModel


class FeatureKey(str, Enum):
    ai_tim_kiem = "ai_tim_kiem"
    giai_bai_tap = "giai_bai_tap"
    ai_viet_van = "ai_viet_van"
    dich = "dich"
    tom_tat = "tom_tat"
    mindmap = "mindmap"


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"


class FeaturePreset(SQLModel, table=True):
    __tablename__ = "feature_preset"
    id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
    )
    key: FeatureKey = Field(index=True, unique=True)
    name: str
    system_prompt: Optional[str] = None
    default_params: dict = Field(
        default_factory=dict,
        sa_column=Column(
            JSONB,
            nullable=False,
            server_default="{}",
        ),
    )
    params_schema: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    conversations: Mapped[list["Conversation"]] = Relationship(
        sa_relationship=relationship(back_populates="feature_preset")
    )


class Conversation(SQLModel, table=True):
    __tablename__ = "conversation"
    id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
    )
    feature_preset_id: UUID = Field(
        foreign_key="feature_preset.id",
        nullable=False,
    )
    title: Optional[str] = None
    feature_params: dict = Field(
        default_factory=dict,
        sa_column=Column(
            JSONB,
            nullable=False,
            server_default="{}",
        ),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    feature_preset: Mapped["FeaturePreset"] = Relationship(
        sa_relationship=relationship(back_populates="conversations")
    )
    messages: Mapped[list["Message"]] = Relationship(
        sa_relationship=relationship(back_populates="conversation"),
    )


class Message(SQLModel, table=True):
    __tablename__ = "message"
    id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
    )
    conversation_id: UUID = Field(foreign_key="conversation.id", nullable=False, index=True)
    role: MessageRole
    content: str
    metadata_: Optional[dict] = Field(
        default=None,
        sa_column=Column("metadata", JSONB),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    conversation: Mapped["Conversation"] = Relationship(
        sa_relationship=relationship(back_populates="messages")
    )
    citations: Mapped[list["MessageCitation"]] = Relationship(
        sa_relationship=relationship(back_populates="message")
    )


class ArticleSource(SQLModel, table=True):
    __tablename__ = "article_source"
    id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
    )
    domain: str = Field(unique=True, index=True)
    name: str
    homepage_url: Optional[str] = None
    rss_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    articles: Mapped[list["Article"]] = Relationship(
        sa_relationship=relationship(back_populates="source")
    )


class Article(SQLModel, table=True):
    __tablename__ = "article"
    id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
    )
    source_id: Optional[UUID] = Field(foreign_key="article_source.id")
    url: str = Field(unique=True, index=True)
    title: str
    author: Optional[str] = None
    content_text: str = Field(sa_column=Column(TEXT, nullable=False))
    content_html: Optional[str] = None
    lang: str = Field(default="vi")
    category: Optional[str] = None
    tags: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(ARRAY(TEXT)),
    )
    image_url: Optional[str] = None
    published_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    metadata_: Optional[dict] = Field(
        default=None,
        sa_column=Column("metadata", JSONB),
    )

    source: Mapped["ArticleSource"] = Relationship(
        sa_relationship=relationship(back_populates="articles")
    )
    citations: Mapped[list["MessageCitation"]] = Relationship(
        sa_relationship=relationship(back_populates="article")
    )


class DailySuggestion(SQLModel, table=True):
    __tablename__ = "daily_suggestion"
    id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
    )
    article_id: UUID = Field(foreign_key="article.id", nullable=False)
    suggestion_date: date
    rank: int
    reason: Optional[str] = None


class MessageCitation(SQLModel, table=True):
    __tablename__ = "message_citation"
    id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
    )
    message_id: UUID = Field(
        foreign_key="message.id",
        nullable=False,
        index=True,
    )
    article_id: UUID = Field(
        foreign_key="article.id",
        nullable=False,
        index=True,
    )
    rank: Optional[int] = None
    offset_start: Optional[int] = None
    offset_end: Optional[int] = None
    snippet: Optional[str] = None

    message: Mapped["Message"] = Relationship(
        sa_relationship=relationship(back_populates="citations")
    )
    article: Mapped["Article"] = Relationship(
        sa_relationship=relationship(back_populates="citations")
    )
