"""Daily rates per role and the contribution margin shared by all roles.

Revision ID: fa67bc89de01
Revises: ef56ab78cd90
Create Date: 2026-10-18 04:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "fa67bc89de01"
down_revision: str | None = "ef56ab78cd90"
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
        "daily_rates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("production_cost", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name="fk_daily_rates_role_id_roles",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("role_id", name="uq_daily_rates_role_id"),
    )
    op.create_table(
        "daily_rate_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "contribution_margin_percent",
            sa.Integer(),
            server_default="35",
            nullable=False,
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "INSERT INTO daily_rate_settings (contribution_margin_percent) VALUES (35)"
    )


def downgrade() -> None:
    op.drop_table("daily_rate_settings")
    op.drop_table("daily_rates")
