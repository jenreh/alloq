"""Normalize risk impact from EUR values to 1-5 score.

Revision ID: 20260508f_norm_risk_impact
Revises: 20260508e_norm_risk_status
Create Date: 2026-05-08
"""

from alembic import op

revision = "20260508f_norm_risk_impact"
down_revision = "20260508d_add_measures"
branch_labels = None
depends_on = None

# EUR tier boundaries used previously
_TIER_1 = 20_000
_TIER_2 = 100_000
_TIER_3 = 500_000
_TIER_4 = 1_000_000

# German UI labels → English enum values
_MAPPING = {
    "Offen": "open",
    "In Bearbeitung": "mitigated",
    "Geschlossen": "resolved",
}

_REVERSE = {v: k for k, v in _MAPPING.items()}


def upgrade() -> None:
    """Convert impact EUR values to 1-5 score."""
    # Values > 5 are old EUR-based values; values 1-5 are already correct.
    op.execute(
        f"""
        UPDATE risks SET impact = CASE
            WHEN impact <= {_TIER_1} THEN 1
            WHEN impact <= {_TIER_2} THEN 2
            WHEN impact <= {_TIER_3} THEN 3
            WHEN impact <= {_TIER_4} THEN 4
            ELSE 5
        END
        WHERE impact > 5
        """  # noqa: S608
    )

    for old, new in _MAPPING.items():
        op.execute(
            f"UPDATE risks SET mitigation_status = '{new}' "  # noqa: S608
            f"WHERE mitigation_status = '{old}'"
        )


def downgrade() -> None:
    """Convert impact 1-5 scores back to representative EUR values."""
    op.execute(
        """
        UPDATE risks SET impact = CASE
            WHEN impact = 1 THEN 10000
            WHEN impact = 2 THEN 60000
            WHEN impact = 3 THEN 300000
            WHEN impact = 4 THEN 750000
            WHEN impact = 5 THEN 1500000
            ELSE impact
        END
        WHERE impact BETWEEN 1 AND 5
        """
    )

    for old, new in _REVERSE.items():
        op.execute(
            f"UPDATE risks SET mitigation_status = '{new}' "  # noqa: S608
            f"WHERE mitigation_status = '{old}'"
        )
