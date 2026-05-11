"""Add public_holidays table with NRW seed data.

Revision ID: bb33cc44dd55
Revises: aa11bb22cc33
Create Date: 2026-05-11 00:00:00.000000

"""

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa

from alembic import op

revision: str = "bb33cc44dd55"
down_revision: str | None = "aa11bb22cc33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_holidays",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "state_code", sa.String(length=10), nullable=False, server_default="NRW"
        ),
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
    )
    op.create_index(
        "ix_public_holidays_date", "public_holidays", ["date"], unique=False
    )
    op.create_index(
        "ix_public_holidays_name", "public_holidays", ["name"], unique=False
    )
    op.create_index(
        "ix_public_holidays_state_code",
        "public_holidays",
        ["state_code"],
        unique=False,
    )

    # ── Seed: NRW Feiertage 2026 ─────────────────────────────────────────────
    # Fixed-date (recurring) holidays
    fixed_2026 = [
        ("Neujahr", date(2026, 1, 1), True),
        ("Tag der Deutschen Einheit", date(2026, 10, 3), True),
        ("Allerheiligen", date(2026, 11, 1), True),
        ("1. Weihnachtstag", date(2026, 12, 25), True),
        ("2. Weihnachtstag", date(2026, 12, 26), True),
        ("Tag der Arbeit", date(2026, 5, 1), True),
    ]
    # Moveable holidays 2026 (based on Easter Sunday 2026 = April 5)
    moveable_2026 = [
        ("Karfreitag", date(2026, 4, 3), False),
        ("Ostersonntag", date(2026, 4, 5), False),
        ("Ostermontag", date(2026, 4, 6), False),
        ("Christi Himmelfahrt", date(2026, 5, 14), False),
        ("Pfingstsonntag", date(2026, 6, 24), False),
        ("Pfingstmontag", date(2026, 6, 25), False),
        ("Fronleichnam", date(2026, 7, 4), False),
    ]

    # Fixed-date (recurring) holidays 2027
    fixed_2027 = [
        ("Neujahr", date(2027, 1, 1), True),
        ("Tag der Deutschen Einheit", date(2027, 10, 3), True),
        ("Allerheiligen", date(2027, 11, 1), True),
        ("1. Weihnachtstag", date(2027, 12, 25), True),
        ("2. Weihnachtstag", date(2027, 12, 26), True),
        ("Tag der Arbeit", date(2027, 5, 1), True),
    ]
    # Moveable holidays 2027 (based on Easter Sunday 2027 = March 28)
    moveable_2027 = [
        ("Karfreitag", date(2027, 3, 26), False),
        ("Ostersonntag", date(2027, 3, 28), False),
        ("Ostermontag", date(2027, 3, 29), False),
        ("Christi Himmelfahrt", date(2027, 5, 6), False),
        ("Pfingstsonntag", date(2027, 5, 16), False),
        ("Pfingstmontag", date(2027, 5, 17), False),
        ("Fronleichnam", date(2027, 5, 27), False),
    ]

    all_holidays = fixed_2026 + moveable_2026 + fixed_2027 + moveable_2027
    rows = [
        {
            "name": name,
            "date": d,
            "is_recurring": is_recurring,
            "state_code": "NRW",
        }
        for name, d, is_recurring in all_holidays
    ]

    op.bulk_insert(
        sa.table(
            "public_holidays",
            sa.column("name", sa.String),
            sa.column("date", sa.Date),
            sa.column("is_recurring", sa.Boolean),
            sa.column("state_code", sa.String),
        ),
        rows,
    )


def downgrade() -> None:
    op.drop_index("ix_public_holidays_state_code", table_name="public_holidays")
    op.drop_index("ix_public_holidays_name", table_name="public_holidays")
    op.drop_index("ix_public_holidays_date", table_name="public_holidays")
    op.drop_table("public_holidays")
