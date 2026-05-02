"""project owners

Revision ID: fd343f955aa8
Revises: 5a34a874fd01
Create Date: 2026-05-02 19:28:10.365905

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fd343f955aa8"
down_revision: str | None = "32a130450068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # create new project_owners table
    op.create_table(
        "project_owners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated",
            sa.DateTime(timezone=True),
            onupdate=sa.func.now(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_owners_project_id"),
        "project_owners",
        ["project_id"],
        unique=False,
    )

    # drop old created_by_id from projects
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint("projects_created_by_id_fkey", type_="foreignkey")
        batch_op.drop_index("ix_projects_created_by_id")
        batch_op.drop_column("created_by_id")


def downgrade() -> None:
    # re-add created_by_id column to projects
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("created_by_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            "ix_projects_created_by_id", ["created_by_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_projects_created_by_id_employees",
            "employees",
            ["created_by_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # drop project_owners table
    op.drop_index(op.f("ix_project_owners_project_id"), table_name="project_owners")
    op.drop_table("project_owners")
