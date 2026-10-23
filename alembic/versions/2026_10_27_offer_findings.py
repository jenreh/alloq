"""Offer workshop findings and commercial values of the workspace.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-10-27 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKSPACE_COLUMNS = (
    "currency",
    "validity_date",
    "price_required",
    "commercials_snapshot",
    "commercials_confirmed_by",
    "commercials_confirmed_at",
)


def upgrade() -> None:
    with op.batch_alter_table("offer_workspaces") as batch:
        batch.add_column(
            sa.Column(
                "currency", sa.String(length=3), server_default="EUR", nullable=False
            )
        )
        batch.add_column(sa.Column("validity_date", sa.Date(), nullable=True))
        batch.add_column(
            sa.Column(
                "price_required",
                sa.Boolean(),
                server_default=sa.true(),
                nullable=False,
            )
        )
        batch.add_column(sa.Column("commercials_snapshot", sa.JSON(), nullable=True))
        batch.add_column(
            sa.Column(
                "commercials_confirmed_by",
                sa.String(length=255),
                server_default="",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "commercials_confirmed_at", sa.DateTime(timezone=True), nullable=True
            )
        )

    op.create_table(
        "offer_findings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("rule", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("target", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("map_revision", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.String(length=255), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["offers.id"],
            name="fk_offer_findings_offer_id_offers",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "offer_id", "fingerprint", name="uq_offer_findings_fingerprint"
        ),
    )
    op.create_index("ix_offer_findings_id", "offer_findings", ["id"])
    op.create_index("ix_offer_findings_offer_id", "offer_findings", ["offer_id"])


def downgrade() -> None:
    op.drop_index("ix_offer_findings_offer_id", table_name="offer_findings")
    op.drop_index("ix_offer_findings_id", table_name="offer_findings")
    op.drop_table("offer_findings")
    with op.batch_alter_table("offer_workspaces") as batch:
        for column in reversed(WORKSPACE_COLUMNS):
            batch.drop_column(column)
