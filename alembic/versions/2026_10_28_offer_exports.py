"""Offer workshop snapshots and Word exports.

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-10-28 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: str | None = "f7a8b9c0d1e2"
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
        "offer_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("map_revision", sa.Integer(), nullable=False),
        sa.Column("template_key", sa.String(length=50), nullable=False),
        sa.Column("template_version", sa.String(length=50), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["offers.id"],
            name="fk_offer_snapshots_offer_id_offers",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("offer_id", "number", name="uq_offer_snapshots_number"),
    )
    op.create_index("ix_offer_snapshots_id", "offer_snapshots", ["id"])
    op.create_index("ix_offer_snapshots_offer_id", "offer_snapshots", ["offer_id"])

    op.create_table(
        "offer_exports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("template_version", sa.String(length=50), nullable=False),
        sa.Column("exporter_version", sa.String(length=20), nullable=False),
        sa.Column("blob_id", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["offers.id"],
            name="fk_offer_exports_offer_id_offers",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["offer_snapshots.id"],
            name="fk_offer_exports_snapshot_id_offer_snapshots",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["blob_id"],
            ["offer_blobs.id"],
            name="fk_offer_exports_blob_id_offer_blobs",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_offer_exports_id", "offer_exports", ["id"])
    op.create_index("ix_offer_exports_offer_id", "offer_exports", ["offer_id"])


def downgrade() -> None:
    op.drop_index("ix_offer_exports_offer_id", table_name="offer_exports")
    op.drop_index("ix_offer_exports_id", table_name="offer_exports")
    op.drop_table("offer_exports")
    op.drop_index("ix_offer_snapshots_offer_id", table_name="offer_snapshots")
    op.drop_index("ix_offer_snapshots_id", table_name="offer_snapshots")
    op.drop_table("offer_snapshots")
