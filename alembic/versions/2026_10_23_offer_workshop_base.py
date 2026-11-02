"""Offer workshop foundation: workspaces, blobs and background jobs.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-10-23 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "offer_workspaces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("template_key", sa.String(length=50), nullable=False),
        sa.Column("template_version", sa.String(length=50), nullable=False),
        sa.Column("vision", sa.Text(), nullable=False),
        sa.Column("roles", sa.JSON(), nullable=False),
        sa.Column("map_revision", sa.Integer(), nullable=False),
        sa.Column("story_seq", sa.Integer(), nullable=False),
        sa.Column("doc_state", sa.String(length=20), nullable=False),
        sa.Column(
            "auto_draft", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["offers.id"],
            name="fk_offer_workspaces_offer_id_offers",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("offer_id", name="uq_offer_workspaces_offer_id"),
    )
    op.create_index("ix_offer_workspaces_id", "offer_workspaces", ["id"])

    op.create_table(
        "offer_blobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("mime", sa.String(length=255), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256", name="uq_offer_blobs_sha256"),
    )
    op.create_index("ix_offer_blobs_id", "offer_blobs", ["id"])

    op.create_table(
        "offer_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("input_revisions", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_class", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["offers.id"],
            name="fk_offer_jobs_offer_id_offers",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_offer_jobs_idempotency_key"),
    )
    op.create_index("ix_offer_jobs_id", "offer_jobs", ["id"])
    op.create_index("ix_offer_jobs_offer_id", "offer_jobs", ["offer_id"])
    op.create_index(
        "ix_offer_jobs_status_run_after", "offer_jobs", ["status", "run_after"]
    )


def downgrade() -> None:
    op.drop_index("ix_offer_jobs_status_run_after", table_name="offer_jobs")
    op.drop_index("ix_offer_jobs_offer_id", table_name="offer_jobs")
    op.drop_index("ix_offer_jobs_id", table_name="offer_jobs")
    op.drop_table("offer_jobs")
    op.drop_index("ix_offer_blobs_id", table_name="offer_blobs")
    op.drop_table("offer_blobs")
    op.drop_index("ix_offer_workspaces_id", table_name="offer_workspaces")
    op.drop_table("offer_workspaces")
