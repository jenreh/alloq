"""Role for desktop users who connect with their own Entra ID token.

Creates ``<database>_app`` (``alloq_app`` in production). It may read and change
every table and sequence, including the ones of later migrations, but may not
change the schema. Database admins (``azure_pg_admin``, which the Entra admins
of the server belong to) get it with ADMIN OPTION, so they can grant it to
other users on the users page of the desktop app.

Only PostgreSQL has roles; on other databases this migration does nothing.

Revision ID: ee66ff77aa88
Revises: dd55ee66ff77
Create Date: 2026-10-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ee66ff77aa88"
down_revision: str | None = "dd55ee66ff77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DATABASE_ADMINS = "azure_pg_admin"

# Runs as the owner of the tables (the login that runs the migrations), the
# only login that may grant on them.
_CREATE_ROLE = sa.text(
    f"""
DO $$
DECLARE
    app_role text := current_database() || '_app';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
        EXECUTE format('CREATE ROLE %I NOLOGIN', app_role);
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), app_role);
    EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', app_role);
    EXECUTE format(
        'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO %I',
        app_role);
    EXECUTE format(
        'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO %I', app_role);
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I', app_role);
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
        'GRANT USAGE, SELECT ON SEQUENCES TO %I', app_role);
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{DATABASE_ADMINS}') THEN
        EXECUTE format('GRANT %I TO {DATABASE_ADMINS} WITH ADMIN OPTION', app_role);
    END IF;
END $$;
"""  # noqa: S608  (constant role name, no user input)
)

_DROP_ROLE = sa.text(
    """
DO $$
DECLARE
    app_role text := current_database() || '_app';
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
            'REVOKE ALL ON TABLES FROM %I', app_role);
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
            'REVOKE ALL ON SEQUENCES FROM %I', app_role);
        EXECUTE format(
            'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', app_role);
        EXECUTE format(
            'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', app_role);
        EXECUTE format('REVOKE ALL ON SCHEMA public FROM %I', app_role);
        EXECUTE format(
            'REVOKE ALL ON DATABASE %I FROM %I', current_database(), app_role);
        EXECUTE format('DROP ROLE %I', app_role);
    END IF;
END $$;
"""
)


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgresql():
        op.get_bind().execute(_CREATE_ROLE)


def downgrade() -> None:
    if _is_postgresql():
        op.get_bind().execute(_DROP_ROLE)
