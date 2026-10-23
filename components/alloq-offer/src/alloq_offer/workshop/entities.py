"""Tables of the offer workshop: workspace, blobs and background jobs."""

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import false

from appkit_commons.database.entities import Base, Entity


class DocState(enum.StrEnum):
    """Review state of the offer document."""

    DRAFT = "Entwurf"
    IN_REVIEW = "In Prüfung"
    FINAL = "Final"


class JobStatus(enum.StrEnum):
    """Lifecycle of a background job."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkspaceEntity(Entity, Base):
    """Workshop state of one offer (one workspace per offer)."""

    __tablename__ = "offer_workspaces"

    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    template_key: Mapped[str] = mapped_column(String(50), nullable=False)
    template_version: Mapped[str] = mapped_column(String(50), nullable=False)
    vision: Mapped[str] = mapped_column(Text, nullable=False, default="")
    roles: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    map_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    story_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    doc_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DocState.DRAFT
    )
    auto_draft: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "offer_id": self.offer_id,
            "template_key": self.template_key,
            "template_version": self.template_version,
            "vision": self.vision,
            "roles": self.roles,
            "map_revision": self.map_revision,
            "story_seq": self.story_seq,
            "doc_state": self.doc_state,
            "auto_draft": self.auto_draft,
            "created_by": self.created_by,
            "created": self.created,
            "updated": self.updated,
        }


class BlobEntity(Entity, Base):
    """File content stored once per SHA-256."""

    __tablename__ = "offer_blobs"

    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime: Mapped[str] = mapped_column(String(255), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


class JobEntity(Entity, Base):
    """Persisted background job of the workshop."""

    __tablename__ = "offer_jobs"
    __table_args__ = (Index("ix_offer_jobs_status_run_after", "status", "run_after"),)

    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=JobStatus.QUEUED
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    input_revisions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "offer_id": self.offer_id,
            "kind": self.kind,
            "status": self.status,
            "idempotency_key": self.idempotency_key,
            "payload": self.payload,
            "input_revisions": self.input_revisions,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "run_after": self.run_after,
            "lease_until": self.lease_until,
            "error_class": self.error_class,
            "error_message": self.error_message,
            "result": self.result,
            "created": self.created,
            "updated": self.updated,
        }
