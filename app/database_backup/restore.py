"""Transactional cleanup, validation, and deployment grant preservation."""

import hashlib
from pathlib import Path
from typing import Any, LiteralString

from psycopg import AsyncConnection, sql

from .configuration import BackupError
from .grant_extras import additional_grants, reset_acl
from .maintenance import MAINTENANCE_LOCK

SCHEMAS = (
    "SELECT nspname, pg_get_userbyid(nspowner) FROM pg_namespace "
    "WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema' "
    "ORDER BY nspname"
)
TRANSIENT_TABLES = (
    "auth_sessions",
    "auth_oauth_states",
    "auth_password_reset_tokens",
    "auth_password_reset_requests",
)


async def cleanup_sql(connection: AsyncConnection) -> str:
    """All destructive statements run inside psql's one transaction."""
    cursor = await connection.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_namespace "
        "WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema' "
        "AND NOT pg_has_role(current_user, nspowner, 'USAGE'))"
    )
    row = await cursor.fetchone()
    if row and row[0]:
        raise BackupError("Der Datenbankbenutzer besitzt nicht alle Anwendungsschemas.")
    statements = ["SET LOCAL lock_timeout='30s';"]
    cursor = await connection.execute(
        "SELECT extname FROM pg_extension WHERE extname <> 'plpgsql' ORDER BY extname"
    )
    for (name,) in await cursor.fetchall():
        statements.append(
            sql.SQL("DROP EXTENSION {} CASCADE;")
            .format(sql.Identifier(name))
            .as_string()
        )
    cursor = await connection.execute(SCHEMAS)
    for name, _owner in await cursor.fetchall():
        statements.append(
            sql.SQL("DROP SCHEMA {} CASCADE;").format(sql.Identifier(name)).as_string()
        )
    statements.append(
        "SELECT pg_catalog.lo_unlink(oid) FROM pg_catalog.pg_largeobject_metadata;"
    )
    # pg_dump omits CREATE SCHEMA public for the standard public schema.
    statements.append("CREATE SCHEMA public;")
    return "\n".join(statements) + "\n"


def authorization_sql(
    user: dict[str, Any], session_id: str, timeout: int, lock_timeout: int
) -> str:
    """The restoring transaction holds maintenance, including if its parent dies."""
    check = (
        sql.SQL(
            "BEGIN IF NOT EXISTS (SELECT 1 FROM public.auth_users u "
            "JOIN public.auth_sessions s ON u.id=s.user_id "
            "WHERE u.id={} AND md5(s.session_id)={} AND s.expires_at>clock_timestamp() "
            "AND u.is_active AND u.is_verified AND u.is_admin "
            "AND NOT u.needs_password_reset AND 'database_backup'=ANY(u.roles) "
            "AND u._password={}) THEN RAISE EXCEPTION 'Backup authorization expired'; "
            "END IF; END"
        )
        .format(
            sql.Literal(user["id"]),
            sql.Literal(
                hashlib.md5(session_id.encode(), usedforsecurity=False).hexdigest()
            ),
            sql.Literal(user["_password"]),
        )
        .as_string()
    )
    return (
        sql.SQL("SET LOCAL statement_timeout={};\n")
        .format(sql.Literal(lock_timeout * 1000))
        .as_string()
        + sql.SQL("SELECT pg_advisory_xact_lock({});\n")
        .format(sql.Literal(MAINTENANCE_LOCK))
        .as_string()
        + sql.SQL("SET LOCAL statement_timeout={};\n")
        .format(sql.Literal(timeout * 1000))
        .as_string()
        + sql.SQL("DO {};\n").format(sql.Literal(check)).as_string()
    )


def do_block(body: str) -> str:
    """Quote the entire body, including identifiers containing dollar delimiters."""
    return sql.SQL("DO {};\n").format(sql.Literal(body)).as_string()


async def deployment_grants(connection: AsyncConnection) -> str:
    """Preserve target grants, never import archive owners or global roles."""
    statements = []
    cursor = await connection.execute(
        "SELECT n.nspname, c.relname, c.relkind, pg_get_userbyid(c.relowner), "
        "a.grantee, a.privilege_type, a.is_grantable "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "LEFT JOIN LATERAL aclexplode(COALESCE(c.relacl, "
        "acldefault((CASE WHEN c.relkind='S' THEN 's' ELSE 'r' END)::\"char\", "
        "c.relowner))) a ON true "
        "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema' "
        "AND c.relkind IN ('r','p','v','m','S')"
    )
    seen = set()
    for (
        schema,
        name,
        kind,
        owner,
        grantee,
        privilege,
        grantable,
    ) in await cursor.fetchall():
        qualified = sql.SQL("{}.{}").format(
            sql.Identifier(schema), sql.Identifier(name)
        )
        if (schema, name) not in seen:
            seen.add((schema, name))
            object_kind = "SEQUENCE" if kind == "S" else "TABLE"
            relation_kinds: dict[str, LiteralString] = {
                "S": "SEQUENCE",
                "v": "VIEW",
                "m": "MATERIALIZED VIEW",
            }
            relation_kind = relation_kinds.get(kind, "TABLE")
            conditional = (
                "BEGIN IF to_regclass({}) IS NOT NULL THEN "
                "ALTER {} {} OWNER TO {}; {} END IF; END"
            )
            reset = reset_acl(
                "pg_class",
                "relacl",
                sql.SQL("to_regclass({})").format(sql.Literal(qualified.as_string())),
                sql.SQL(object_kind),
                qualified,
            )
            # The reset itself is a complete DO statement and handles absent OIDs.
            statements.append(
                do_block(
                    sql.SQL(conditional)
                    .format(
                        sql.Literal(qualified.as_string()),
                        sql.SQL(relation_kind),
                        qualified,
                        sql.Identifier(owner),
                        reset,
                    )
                    .as_string()
                )
            )
        if grantee is None:
            continue
        role_cursor = await connection.execute("SELECT pg_get_userbyid(%s)", (grantee,))
        role = await role_cursor.fetchone()
        if role is None:
            raise BackupError(
                "Die Datenbankberechtigungen konnten nicht geprüft werden."
            )
        recipient = sql.SQL("PUBLIC") if grantee == 0 else sql.Identifier(role[0])
        grant = sql.SQL("GRANT {} ON {} {} TO {}{}").format(
            sql.SQL(privilege),
            sql.SQL("SEQUENCE" if kind == "S" else "TABLE"),
            qualified,
            recipient,
            sql.SQL(" WITH GRANT OPTION" if grantable else ""),
        )
        statements.append(
            do_block(
                sql.SQL("BEGIN IF to_regclass({}) IS NOT NULL THEN {}; END IF; END")
                .format(sql.Literal(qualified.as_string()), grant)
                .as_string()
            )
        )
    cursor = await connection.execute(SCHEMAS)
    for schema, owner in await cursor.fetchall():
        statements.append(
            do_block(
                sql.SQL(
                    "BEGIN IF EXISTS (SELECT 1 FROM pg_namespace "
                    "WHERE nspname={}) THEN ALTER SCHEMA {} OWNER TO {}; END IF; END"
                )
                .format(
                    sql.Literal(schema), sql.Identifier(schema), sql.Identifier(owner)
                )
                .as_string()
            )
        )
    cursor = await connection.execute(
        "SELECT nspname FROM pg_namespace "
        "WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'"
    )
    for (schema,) in await cursor.fetchall():
        target = sql.Identifier(schema)
        reset = reset_acl(
            "pg_namespace",
            "nspacl",
            sql.SQL("to_regnamespace({})").format(sql.Literal(schema)),
            sql.SQL("SCHEMA"),
            target,
        )
        statements.append(
            do_block(
                sql.SQL("BEGIN IF to_regnamespace({}) IS NOT NULL THEN {} END IF; END")
                .format(sql.Literal(schema), reset)
                .as_string()
            )
        )
    cursor = await connection.execute(
        "SELECT n.nspname, a.grantee, a.privilege_type, a.is_grantable "
        "FROM pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) a "
        "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'"
    )
    for schema, grantee, privilege, grantable in await cursor.fetchall():
        role_cursor = await connection.execute("SELECT pg_get_userbyid(%s)", (grantee,))
        role = await role_cursor.fetchone()
        if role is None:
            raise BackupError(
                "Die Datenbankberechtigungen konnten nicht geprüft werden."
            )
        recipient = sql.SQL("PUBLIC") if grantee == 0 else sql.Identifier(role[0])
        statements.append(
            do_block(
                sql.SQL(
                    "BEGIN IF EXISTS (SELECT 1 FROM pg_namespace "
                    "WHERE nspname={}) THEN GRANT {} ON SCHEMA {} TO {}{}; END IF; END"
                )
                .format(
                    sql.Literal(schema),
                    sql.SQL(privilege),
                    sql.Identifier(schema),
                    recipient,
                    sql.SQL(" WITH GRANT OPTION" if grantable else ""),
                )
                .as_string()
            )
        )
    statements.append(await additional_grants(connection))
    return "\n".join(statements)


def finalize_sql(manifest: dict[str, Any], grants: str) -> str:
    checks = []
    for schema, name, count in manifest["tables"]:
        checks.append(
            sql.SQL(
                "IF (SELECT count(*) FROM {}.{}) <> {} THEN "
                "RAISE EXCEPTION 'Backup validation failed'; END IF;"
            )
            .format(sql.Identifier(schema), sql.Identifier(name), sql.Literal(count))
            .as_string()
        )
    checks.append(
        sql.SQL(
            "IF (SELECT array_agg(version_num ORDER BY version_num) "
            "FROM public.alembic_version) IS DISTINCT FROM {}::varchar[] THEN "
            "RAISE EXCEPTION 'Backup revision mismatch'; END IF;"
        )
        .format(sql.Literal(manifest["revision"]))
        .as_string()
    )
    statements = [do_block("BEGIN " + "\n".join(checks) + " END")]
    statements.extend(
        sql.SQL("DELETE FROM public.{};").format(sql.Identifier(name)).as_string()
        for name in TRANSIENT_TABLES
    )
    statements.append(grants)
    return "\n".join(statements) + "\n"


def transaction_script(directory: Path, cleanup: str, final: str, limit: int) -> Path:
    """Inject into pg_restore --single-transaction's outer BEGIN/COMMIT.

    pg_restore -1 emits one outer transaction including large objects. Its
    setup resets timeouts, so inject limits AFTER that setup. Inspect only the
    generated prefix/footer: COPY rows may themselves contain 'COMMIT;'.
    """
    source_path, destination = directory / "restore.sql", directory / "transaction.sql"
    window, written = 65536, 0
    begin, commit = b"\nBEGIN;\n", b"\nCOMMIT;\n"
    with source_path.open("rb") as source, destination.open("xb") as target:
        destination.chmod(0o600)

        def write(data: bytes) -> None:
            nonlocal written
            written += len(data)
            if written > limit:
                raise BackupError("Das Wiederherstellungsskript ist zu groß.")
            target.write(data)

        prefix = source.read(window)
        start = prefix.find(begin)
        if start < 0:
            raise BackupError(
                "Das Wiederherstellungsskript hat kein Transaktionsformat."
            )
        setup = b"\nSET row_security = off;\n"
        setup_end = prefix.find(setup, start)
        if setup_end < 0:
            raise BackupError("Das Wiederherstellungsskript hat kein Setup-Format.")
        end = setup_end + len(setup)
        write(prefix[:end])
        write(cleanup.encode())
        buffer = prefix[end:]
        while chunk := source.read(1024 * 1024):
            buffer += chunk
            if len(buffer) > window:
                write(buffer[:-window])
                buffer = buffer[-window:]
        stop = buffer.rfind(commit)
        if stop < 0:
            raise BackupError("Das Wiederherstellungsskript ist unvollständig.")
        write(buffer[:stop])
        write(b"\n" + final.encode())
        write(buffer[stop:])
    return destination
