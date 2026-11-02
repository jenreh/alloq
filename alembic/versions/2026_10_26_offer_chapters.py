"""Offer workshop chapters, chapter revisions and proposals.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-10-26 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("offer_proposals", "offer_chapter_revisions", "offer_chapters")


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
        "offer_chapters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("chapter_key", sa.String(length=50), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("protected", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "needs_review", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("review_reason", sa.Text(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["offers.id"],
            name="fk_offer_chapters_offer_id_offers",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("offer_id", "chapter_key", name="uq_offer_chapters_key"),
    )
    op.create_index("ix_offer_chapters_id", "offer_chapters", ["id"])
    op.create_index("ix_offer_chapters_offer_id", "offer_chapters", ["offer_id"])

    op.create_table(
        "offer_chapter_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chapter_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("map_revision", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["offer_chapters.id"],
            name="fk_offer_chapter_revisions_chapter_id_offer_chapters",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("chapter_id", "number", name="uq_offer_chapter_revisions"),
    )
    op.create_index("ix_offer_chapter_revisions_id", "offer_chapter_revisions", ["id"])
    op.create_index(
        "ix_offer_chapter_revisions_chapter_id",
        "offer_chapter_revisions",
        ["chapter_id"],
    )

    op.create_table(
        "offer_proposals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("chapter_key", sa.String(length=50), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("map_revision", sa.Integer(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["offers.id"],
            name="fk_offer_proposals_offer_id_offers",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["offer_jobs.id"],
            name="fk_offer_proposals_job_id_offer_jobs",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_offer_proposals_id", "offer_proposals", ["id"])
    op.create_index("ix_offer_proposals_offer_id", "offer_proposals", ["offer_id"])


def downgrade() -> None:
    for table in TABLES:
        for index in {
            "offer_proposals": ("ix_offer_proposals_offer_id", "ix_offer_proposals_id"),
            "offer_chapter_revisions": (
                "ix_offer_chapter_revisions_chapter_id",
                "ix_offer_chapter_revisions_id",
            ),
            "offer_chapters": ("ix_offer_chapters_offer_id", "ix_offer_chapters_id"),
        }[table]:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
