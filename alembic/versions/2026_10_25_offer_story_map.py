"""Offer workshop story map: activities, tasks, stories, statements, revisions.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-10-25 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "offer_generation_runs",
    "offer_map_revisions",
    "offer_statements",
    "offer_stories",
    "offer_tasks",
    "offer_activities",
    "offer_slices",
)


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
    ]


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


def _offer_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["offer_id"],
        ["offers.id"],
        name=f"fk_{table}_offer_id_offers",
        ondelete="RESTRICT",
    )


def _fk(
    table: str, column: str, target: str, ondelete: str = "RESTRICT"
) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column],
        [f"{target}.id"],
        name=f"fk_{table}_{column}_{target}",
        ondelete=ondelete,
    )


def _indexes(table: str) -> None:
    op.create_index(f"ix_{table}_id", table, ["id"])
    op.create_index(f"ix_{table}_offer_id", table, ["offer_id"])


def upgrade() -> None:
    op.create_table(
        "offer_slices",
        *_base(),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        _offer_fk("offer_slices"),
    )
    _indexes("offer_slices")

    op.create_table(
        "offer_activities",
        *_base(),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        _offer_fk("offer_activities"),
    )
    _indexes("offer_activities")

    op.create_table(
        "offer_tasks",
        *_base(),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        _offer_fk("offer_tasks"),
        _fk("offer_tasks", "activity_id", "offer_activities"),
    )
    _indexes("offer_tasks")

    op.create_table(
        "offer_stories",
        *_base(),
        sa.Column("key", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("role", sa.String(length=300), nullable=False),
        sa.Column("goal", sa.String(length=300), nullable=False),
        sa.Column("benefit", sa.String(length=300), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("slice_id", sa.Integer(), nullable=True),
        sa.Column("skeleton", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("split_from_id", sa.Integer(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        _offer_fk("offer_stories"),
        _fk("offer_stories", "task_id", "offer_tasks"),
        _fk("offer_stories", "slice_id", "offer_slices"),
        _fk("offer_stories", "split_from_id", "offer_stories"),
        sa.UniqueConstraint("offer_id", "key", name="uq_offer_stories_offer_key"),
    )
    _indexes("offer_stories")

    op.create_table(
        "offer_statements",
        *_base(),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column(
            "needs_recheck", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("confirmed_by", sa.String(length=255), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        _offer_fk("offer_statements"),
    )
    _indexes("offer_statements")

    op.create_table(
        "offer_map_revisions",
        *_base(),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        _offer_fk("offer_map_revisions"),
        sa.UniqueConstraint("offer_id", "revision", name="uq_offer_map_revisions"),
    )
    _indexes("offer_map_revisions")

    op.create_table(
        "offer_generation_runs",
        *_base(),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("input_revisions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        _offer_fk("offer_generation_runs"),
        _fk("offer_generation_runs", "job_id", "offer_jobs", "SET NULL"),
    )
    _indexes("offer_generation_runs")


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"ix_{table}_offer_id", table_name=table)
        op.drop_index(f"ix_{table}_id", table_name=table)
        op.drop_table(table)
