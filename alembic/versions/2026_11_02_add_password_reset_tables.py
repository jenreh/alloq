"""Add the appkit-user password reset tables.

appkit-user stores reset tokens, the password history and the reset requests in
these tables, but no migration here created them. Password reset and the forced
password change of the seeded admin fail without them.

The columns follow the appkit-user entities. appkit's own migration creates
``created`` and ``updated`` without a time zone; the entities declare them with one.
A table that already exists is left as it is.

Revision ID: 4e7a1c9b2d60
Revises: d9c4081a9088
Create Date: 2026-11-02 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4e7a1c9b2d60"  # pragma: allowlist secret
down_revision: str | None = "d9c4081a9088"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TOKENS = "auth_password_reset_tokens"
_HISTORY = "auth_password_history"
_REQUESTS = "auth_password_reset_requests"
_EXPIRES_INDEX = "idx_password_reset_tokens_token_expires"
_USER_INDEX = "idx_password_reset_tokens_user_id_used"
_HISTORY_INDEX = "idx_password_history_user_id_changed"
# From appkit's migration, not on the entity: anyone can add request rows through
# the public reset page, and each request counts them per email.
_REQUEST_EMAIL_INDEX = "idx_password_reset_requests_email_created"
_REQUEST_CREATED_INDEX = "idx_password_reset_requests_created"


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ]


def _create_tokens() -> None:
    op.create_table(
        _TOKENS,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("reset_type", sa.String(length=50), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_users.id"],
            name="fk_password_reset_tokens_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_password_reset_tokens"),
        sa.UniqueConstraint("token", name="uq_password_reset_tokens_token"),
    )
    op.create_index(_EXPIRES_INDEX, _TOKENS, ["token", "expires_at"])
    op.create_index(_USER_INDEX, _TOKENS, ["user_id", "is_used"])


def _create_history() -> None:
    op.create_table(
        _HISTORY,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("password_hash", sa.String(length=200), nullable=False),
        sa.Column(
            "changed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("change_reason", sa.String(length=50), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_users.id"],
            name="fk_password_history_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_password_history"),
        sa.UniqueConstraint(
            "user_id", "password_hash", name="uq_password_history_user_hash"
        ),
    )
    op.create_index(_HISTORY_INDEX, _HISTORY, ["user_id", "changed_at"])


def _create_requests() -> None:
    op.create_table(
        _REQUESTS,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_password_reset_requests"),
    )
    op.create_index(_REQUEST_EMAIL_INDEX, _REQUESTS, ["email", "created"])
    op.create_index(_REQUEST_CREATED_INDEX, _REQUESTS, ["created"])


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table, create in (
        (_TOKENS, _create_tokens),
        (_HISTORY, _create_history),
        (_REQUESTS, _create_requests),
    ):
        if not inspector.has_table(table):
            create()


def downgrade() -> None:
    op.drop_index(_REQUEST_CREATED_INDEX, table_name=_REQUESTS)
    op.drop_index(_REQUEST_EMAIL_INDEX, table_name=_REQUESTS)
    op.drop_table(_REQUESTS)
    op.drop_index(_HISTORY_INDEX, table_name=_HISTORY)
    op.drop_table(_HISTORY)
    op.drop_index(_USER_INDEX, table_name=_TOKENS)
    op.drop_index(_EXPIRES_INDEX, table_name=_TOKENS)
    op.drop_table(_TOKENS)
