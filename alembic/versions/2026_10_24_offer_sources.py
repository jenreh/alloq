"""Offer workshop sources and their extracted blocks.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-10-24 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b3c4d5e6f7a8"
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
        "offer_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=255), nullable=False),
        sa.Column("blob_id", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("replaces_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("status_detail", sa.Text(), nullable=False),
        sa.Column("included", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["offers.id"],
            name="fk_offer_sources_offer_id_offers",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["blob_id"],
            ["offer_blobs.id"],
            name="fk_offer_sources_blob_id_offer_blobs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["replaces_id"],
            ["offer_sources.id"],
            name="fk_offer_sources_replaces_id_offer_sources",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_offer_sources_id", "offer_sources", ["id"])
    op.create_index("ix_offer_sources_offer_id", "offer_sources", ["offer_id"])
    op.create_index(
        "ix_offer_sources_offer_sha256", "offer_sources", ["offer_id", "sha256"]
    )

    op.create_table(
        "offer_source_blocks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("anchor", sa.JSON(), nullable=False),
        sa.Column("speaker", sa.String(length=50), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["offer_sources.id"],
            name="fk_offer_source_blocks_source_id_offer_sources",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_offer_source_blocks_id", "offer_source_blocks", ["id"])
    op.create_index(
        "ix_offer_source_blocks_source_id", "offer_source_blocks", ["source_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_offer_source_blocks_source_id", table_name="offer_source_blocks")
    op.drop_index("ix_offer_source_blocks_id", table_name="offer_source_blocks")
    op.drop_table("offer_source_blocks")
    op.drop_index("ix_offer_sources_offer_sha256", table_name="offer_sources")
    op.drop_index("ix_offer_sources_offer_id", table_name="offer_sources")
    op.drop_index("ix_offer_sources_id", table_name="offer_sources")
    op.drop_table("offer_sources")
