"""Tables of offer templates: chapter blocks, templates, versions and AI prompts.

Templates are edited as a draft outline and published as immutable versions; an
offer binds one version and copies its outline into its own chapters (spec 6.1).
"""

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import true

from appkit_commons.database.entities import Base, Entity


class ChapterBlockEntity(Entity, Base):
    """A reusable chapter of the library with its content and AI settings."""

    __tablename__ = "offer_chapter_blocks"

    key: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    chapter_type: Mapped[str] = mapped_column(String(20), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    default_content: Mapped[dict] = mapped_column(JSON, nullable=False)
    guiding_question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_rules: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    required_info: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    checks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "key": self.key,
            "title": self.title,
            "chapter_type": self.chapter_type,
            "level": self.level,
            "default_content": self.default_content,
            "guiding_question": self.guiding_question,
            "content_rules": self.content_rules,
            "prompt_text": self.prompt_text,
            "required_info": self.required_info,
            "checks": self.checks,
            "active": self.active,
        }


class OfferTemplateEntity(Entity, Base):
    """A template: its draft outline lives in ``offer_template_chapters``."""

    __tablename__ = "offer_templates"

    key: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    draft_layout_blob_id: Mapped[int | None] = mapped_column(
        ForeignKey("offer_blobs.id", ondelete="RESTRICT"), nullable=True
    )
    frame_before: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    frame_after: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "active": self.active,
            "draft_layout_blob_id": self.draft_layout_blob_id,
            "frame_before": self.frame_before,
            "frame_after": self.frame_after,
        }


class OfferTemplateChapterEntity(Entity, Base):
    """One entry of a template's draft outline."""

    __tablename__ = "offer_template_chapters"
    __table_args__ = (
        UniqueConstraint(
            "template_id", "block_id", name="uq_offer_template_chapters_block"
        ),
    )

    template_id: Mapped[int] = mapped_column(
        ForeignKey("offer_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    block_id: Mapped[int] = mapped_column(
        ForeignKey("offer_chapter_blocks.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "template_id": self.template_id,
            "block_id": self.block_id,
            "position": self.position,
            "required": self.required,
            "title": self.title,
            "level": self.level,
        }


class OfferTemplateVersionEntity(Entity, Base):
    """A published template: outline with resolved block settings; never changed."""

    __tablename__ = "offer_template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "number", name="uq_offer_template_versions"),
    )

    template_id: Mapped[int] = mapped_column(
        ForeignKey("offer_templates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    layout_blob_id: Mapped[int] = mapped_column(
        ForeignKey("offer_blobs.id", ondelete="RESTRICT"), nullable=False
    )
    published_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "template_id": self.template_id,
            "number": self.number,
            "payload": self.payload,
            "layout_blob_id": self.layout_blob_id,
            "published_by": self.published_by,
            "created": self.created,
        }


class PromptEntity(Entity, Base):
    """A version of a global AI system prompt; one version per name is active."""

    __tablename__ = "offer_prompts"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_offer_prompts_version"),
        Index(
            "uq_offer_prompts_active",
            "name",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active"),
        ),
    )

    name: Mapped[str] = mapped_column(String(30), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "text": self.text,
            "active": self.active,
            "author": self.author,
            "created": self.created,
        }
