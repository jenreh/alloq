"""Add anmerkung to project_statuses; reshape risks (typed scoring + measures).

Revision ID: 20260508d_add_measures
Revises: 20260507_abbr
Create Date: 2026-05-08
"""

import sqlalchemy as sa

from alembic import op

revision = "20260508d_add_measures"
down_revision = "20260507_abbr"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_statuses",
        sa.Column("anmerkung", sa.String(2000), nullable=True, server_default=None),
    )

    op.drop_column("risks", "severity")
    op.drop_column("risks", "owner")
    op.drop_column("risks", "probability")
    op.drop_column("risks", "impact")
    op.drop_column("risks", "mitigation_status")

    op.add_column(
        "risks",
        sa.Column("probability", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "risks",
        sa.Column("impact", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "risks",
        sa.Column(
            "mitigation_status",
            sa.String(30),
            nullable=False,
            server_default="Offen",
        ),
    )
    op.add_column(
        "risks",
        sa.Column("measures", sa.String(2000), nullable=True, server_default=None),
    )


def downgrade() -> None:
    op.drop_column("risks", "measures")
    op.drop_column("risks", "mitigation_status")
    op.drop_column("risks", "impact")
    op.drop_column("risks", "probability")

    op.add_column(
        "risks",
        sa.Column(
            "mitigation_status", sa.String(20), nullable=False, server_default="open"
        ),
    )
    op.add_column(
        "risks",
        sa.Column("impact", sa.String(20), nullable=False, server_default="medium"),
    )
    op.add_column(
        "risks",
        sa.Column(
            "probability", sa.String(20), nullable=False, server_default="medium"
        ),
    )
    op.add_column(
        "risks",
        sa.Column("owner", sa.String(255), nullable=True),
    )
    op.add_column(
        "risks",
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
    )

    op.drop_column("project_statuses", "anmerkung")
