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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import false, true

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


class SourceKind(enum.StrEnum):
    """What a customer source is."""

    TEXT = "text"
    EML = "eml"
    TXT = "txt"
    HTML = "html"
    DOCX = "docx"
    PDF = "pdf"
    PPTX = "pptx"
    AUDIO = "audio"


class SourceStatus(enum.StrEnum):
    """Processing state of a source, shown to users as is."""

    UPLOADED = "hochgeladen"
    PROCESSING = "in Verarbeitung"
    USABLE = "nutzbar"
    PARTIAL = "teilweise nutzbar"
    FAILED = "fehlgeschlagen"
    MANUAL = "manuell nötig"


class Scope(enum.StrEnum):
    """How far a story is part of the offer."""

    OPEN = "offen"
    OFFERED = "angeboten"
    OPTION = "option"
    EXCLUDED = "ausgeschlossen"


class Origin(enum.StrEnum):
    """Where a story comes from."""

    CUSTOMER = "Kunde"
    PROPOSAL = "Vorschlag"
    USER = "Nutzer"


class StatementType(enum.StrEnum):
    REQUIREMENT = "Kundenanforderung"
    FACT = "Belegter Sachverhalt"
    SOLUTION = "Lösungsvorschlag"
    ASSUMPTION = "Annahme"
    OPEN_POINT = "Offener Punkt/Konflikt"
    CONFLICT = "Widerspruch"


class StatementStatus(enum.StrEnum):
    PROPOSED = "Vorschlag"
    CONFIRMED = "Bestätigt"


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


class SourceEntity(Entity, Base):
    """A customer source (pasted text or uploaded file) of one offer."""

    __tablename__ = "offer_sources"
    __table_args__ = (Index("ix_offer_sources_offer_sha256", "offer_id", "sha256"),)

    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    mime: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    blob_id: Mapped[int | None] = mapped_column(
        ForeignKey("offer_blobs.id", ondelete="RESTRICT"), nullable=True
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    replaces_id: Mapped[int | None] = mapped_column(
        ForeignKey("offer_sources.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=SourceStatus.UPLOADED
    )
    status_detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    included: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "offer_id": self.offer_id,
            "kind": self.kind,
            "title": self.title,
            "filename": self.filename,
            "mime": self.mime,
            "blob_id": self.blob_id,
            "sha256": self.sha256,
            "version": self.version,
            "replaces_id": self.replaces_id,
            "status": self.status,
            "status_detail": self.status_detail,
            "included": self.included,
            "revoked_at": self.revoked_at,
            "created_by": self.created_by,
            "created": self.created,
            "updated": self.updated,
        }


class SourceBlockEntity(Entity, Base):
    """A citable piece of a source; a ``gap`` block records what was not read."""

    __tablename__ = "offer_source_blocks"

    source_id: Mapped[int] = mapped_column(
        ForeignKey("offer_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    anchor: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    speaker: Mapped[str | None] = mapped_column(String(50), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "seq": self.seq,
            "kind": self.kind,
            "anchor": self.anchor,
            "speaker": self.speaker,
            "text": self.text,
        }


class SliceEntity(Entity, Base):
    """A proposed implementation slice of the map."""

    __tablename__ = "offer_slices"

    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "offer_id": self.offer_id,
            "title": self.title,
            "position": self.position,
        }


class ActivityEntity(Entity, Base):
    """A customer activity: one column of the story map."""

    __tablename__ = "offer_activities"

    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "offer_id": self.offer_id,
            "title": self.title,
            "position": self.position,
            "archived_at": self.archived_at,
        }


class TaskEntity(Entity, Base):
    """A task below an activity."""

    __tablename__ = "offer_tasks"

    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("offer_activities.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "offer_id": self.offer_id,
            "activity_id": self.activity_id,
            "title": self.title,
            "position": self.position,
            "archived_at": self.archived_at,
        }


class StoryEntity(Entity, Base):
    """A simple user story; its key never changes and is never reused."""

    __tablename__ = "offer_stories"
    __table_args__ = (
        UniqueConstraint("offer_id", "key", name="uq_offer_stories_offer_key"),
    )

    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    role: Mapped[str] = mapped_column(String(300), nullable=False)
    goal: Mapped[str] = mapped_column(String(300), nullable=False)
    benefit: Mapped[str] = mapped_column(String(300), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default=Scope.OPEN)
    origin: Mapped[str] = mapped_column(String(20), nullable=False)
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("offer_tasks.id", ondelete="RESTRICT"), nullable=True
    )
    slice_id: Mapped[int | None] = mapped_column(
        ForeignKey("offer_slices.id", ondelete="RESTRICT"), nullable=True
    )
    skeleton: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    split_from_id: Mapped[int | None] = mapped_column(
        ForeignKey("offer_stories.id", ondelete="RESTRICT"), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "offer_id": self.offer_id,
            "key": self.key,
            "title": self.title,
            "role": self.role,
            "goal": self.goal,
            "benefit": self.benefit,
            "scope": self.scope,
            "origin": self.origin,
            "task_id": self.task_id,
            "slice_id": self.slice_id,
            "skeleton": self.skeleton,
            "priority": self.priority,
            "position": self.position,
            "source_refs": self.source_refs,
            "split_from_id": self.split_from_id,
            "archived_at": self.archived_at,
        }


class StatementEntity(Entity, Base):
    """A briefing statement: requirement, fact, proposal, assumption or open point."""

    __tablename__ = "offer_statements"

    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatementStatus.PROPOSED
    )
    source_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    needs_recheck: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    confirmed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "offer_id": self.offer_id,
            "type": self.type,
            "text": self.text,
            "status": self.status,
            "source_refs": self.source_refs,
            "needs_recheck": self.needs_recheck,
            "confirmed_by": self.confirmed_by,
            "confirmed_at": self.confirmed_at,
        }


class MapRevisionEntity(Entity, Base):
    """Immutable snapshot of the map after one change."""

    __tablename__ = "offer_map_revisions"
    __table_args__ = (
        UniqueConstraint("offer_id", "revision", name="uq_offer_map_revisions"),
    )

    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "offer_id": self.offer_id,
            "revision": self.revision,
            "snapshot": self.snapshot,
            "created_by": self.created_by,
            "created": self.created,
        }


class GenerationRunEntity(Entity, Base):
    """Which model and prompt version produced a proposal."""

    __tablename__ = "offer_generation_runs"

    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("offer_jobs.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    input_revisions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "offer_id": self.offer_id,
            "job_id": self.job_id,
            "kind": self.kind,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "input_revisions": self.input_revisions,
            "status": self.status,
            "created": self.created,
        }
