"""Enforce absence date ranges and one capacity row per assignment.

``absences`` gets ``CHECK (end_date >= start_date)``. Existing reversed rows are
repaired by swapping start and end date before the constraint is created.

``capacities`` gets a unique constraint on (project_id, employee_id, role_id),
the key the application already treats as one assignment. Duplicates are merged
into the row with the lowest id, widened to the union of their date ranges;
the other rows are deleted. The merge is not undone on downgrade.

Revision ID: dd55ee66ff77
Revises: cc44dd55ee66
Create Date: 2026-09-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "dd55ee66ff77"
down_revision: str | None = "cc44dd55ee66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ABSENCE_RANGE_CHECK = "ck_absences_date_range"
CAPACITY_UNIQUE = "uq_capacities_proj_emp_role"

_SWAP_REVERSED_ABSENCES = sa.text(
    "UPDATE absences SET start_date = end_date, end_date = start_date "
    "WHERE end_date < start_date"
)
_SAME_ASSIGNMENT = (
    "FROM capacities AS other "
    "WHERE other.project_id = capacities.project_id "
    "AND other.employee_id = capacities.employee_id "
    "AND other.role_id = capacities.role_id"
)
_KEPT_IDS = "SELECT MIN(id) FROM capacities GROUP BY project_id, employee_id, role_id"
_WIDEN_KEPT_CAPACITIES = sa.text(
    f"UPDATE capacities SET "  # noqa: S608 - constant SQL fragments only
    f"start_date = (SELECT MIN(other.start_date) {_SAME_ASSIGNMENT}), "
    f"end_date = (SELECT MAX(other.end_date) {_SAME_ASSIGNMENT}) "
    f"WHERE id IN ({_KEPT_IDS} HAVING COUNT(*) > 1)"
)
_DELETE_DUPLICATE_CAPACITIES = sa.text(
    f"DELETE FROM capacities WHERE id NOT IN ({_KEPT_IDS})"  # noqa: S608
)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(_SWAP_REVERSED_ABSENCES)
    with op.batch_alter_table("absences", schema=None) as batch_op:
        batch_op.create_check_constraint(ABSENCE_RANGE_CHECK, "end_date >= start_date")

    bind.execute(_WIDEN_KEPT_CAPACITIES)
    bind.execute(_DELETE_DUPLICATE_CAPACITIES)
    with op.batch_alter_table("capacities", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            CAPACITY_UNIQUE, ["project_id", "employee_id", "role_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("capacities", schema=None) as batch_op:
        batch_op.drop_constraint(CAPACITY_UNIQUE, type_="unique")
    with op.batch_alter_table("absences", schema=None) as batch_op:
        batch_op.drop_constraint(ABSENCE_RANGE_CHECK, type_="check")
