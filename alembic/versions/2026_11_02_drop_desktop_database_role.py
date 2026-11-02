"""Drop the database role of the removed desktop app.

Only desktop users connected with ``<database>_app`` (``alloq_app`` in
production). The web app uses its own login, which keeps its rights. The role's
rights are revoked first, then it is dropped. A step can fail, for example when
another login owns a table or granted the role something. A leftover role must
not stop the deployment (``start.sh`` migrates before the app starts), so such a
failure is only a warning and the other steps still run. Afterwards
``SELECT rolname FROM pg_roles`` shows whether the role is gone.

The downgrade restores the role and its rights, but not who was a member of it.

Only PostgreSQL has roles; on other databases this migration does nothing.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-11-02 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3a4b5c6d7e8"
down_revision: str | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Runs as the owner of the tables (the login that runs the migrations), the
# only login that may revoke on them.
_DROP_ROLE = sa.text(
    """
DO $$
DECLARE
    app_role text := current_database() || '_app';
    step text;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
        FOREACH step IN ARRAY ARRAY[
            'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %1$I',
            'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %1$I',
            'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %1$I',
            'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %1$I',
            'REVOKE ALL ON SCHEMA public FROM %1$I',
            'REVOKE ALL ON DATABASE %2$I FROM %1$I',
            'DROP ROLE %1$I'
        ] LOOP
            BEGIN
                EXECUTE format(step, app_role, current_database());
            EXCEPTION
                WHEN dependent_objects_still_exist OR insufficient_privilege THEN
                    RAISE WARNING 'Role % not fully removed: %', app_role, SQLERRM;
            END;
        END LOOP;
    END IF;
END $$;
"""
)

_RESTORE_ROLE = sa.text(
    """
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
    -- Published versions and prompt history are never rewritten.
    EXECUTE format(
        'REVOKE UPDATE, DELETE ON offer_template_versions FROM %I', app_role);
    EXECUTE format('REVOKE DELETE ON offer_prompts FROM %I', app_role);
END $$;
"""
)


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgresql():
        op.get_bind().execute(_DROP_ROLE)


def downgrade() -> None:
    if _is_postgresql():
        op.get_bind().execute(_RESTORE_ROLE)
