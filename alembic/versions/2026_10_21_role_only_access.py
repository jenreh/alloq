"""Grant planning roles to admins and project managers (role-only access).

Access now depends on roles alone: the admin switch opens only the
administration, and a project manager needs the employee role to read the
planning. So nobody loses access on deploy, every admin gets the
``project_manager`` and ``employee`` roles, and every project manager gets the
``employee`` role.

Revision ID: e023b4c5d6f7
Revises: df12a3b4c5e6
Create Date: 2026-10-21 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from appkit_commons.database.entities import ArrayType

from alembic import op

revision: str = "e023b4c5d6f7"
down_revision: str | None = "df12a3b4c5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROJECT_MANAGER = "project_manager"
EMPLOYEE = "employee"

_users = sa.table(
    "auth_users",
    sa.column("id", sa.Integer),
    sa.column("is_admin", sa.Boolean),
    sa.column("roles", ArrayType()),
)


def granted_roles(roles: list[str], *, is_admin: bool) -> list[str]:
    """``roles`` plus the roles the old admin/manager rules implied."""
    added = []
    if is_admin:
        added.append(PROJECT_MANAGER)
    if is_admin or PROJECT_MANAGER in roles:
        added.append(EMPLOYEE)
    return [*roles, *(role for role in added if role not in roles)]


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.select(_users.c.id, _users.c.is_admin, _users.c.roles))
    for user_id, is_admin, roles in rows.all():
        current = list(roles or [])
        updated = granted_roles(current, is_admin=bool(is_admin))
        if updated != current:
            bind.execute(
                _users.update().where(_users.c.id == user_id).values(roles=updated)
            )


def downgrade() -> None:
    # The granted roles stay: the old rules already gave admins and project
    # managers this access, and removing them could drop roles set by hand.
    pass
