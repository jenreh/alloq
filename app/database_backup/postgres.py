"""Restricted clients and metadata for the configured PostgreSQL database."""

import asyncio
import hashlib
import os
import re
import shutil
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import anyio
from psycopg import AsyncConnection, sql
from sqlalchemy.engine import make_url

from appkit_commons.database.configuration import DatabaseConfig

from .configuration import BackupConfig, BackupError
from .maintenance import MAINTENANCE_LOCK, OPERATION_LOCK

TABLES = (
    "SELECT n.nspname, c.relname FROM pg_class c "
    "JOIN pg_namespace n ON n.oid=c.relnamespace "
    "WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema' "
    "AND c.relkind IN ('r','p','m') "
    "ORDER BY n.nspname, c.relname"
)


def connection_parameters(database: DatabaseConfig) -> dict[str, Any]:
    if database.type != "postgresql":
        raise BackupError("Datenbanksicherungen benötigen PostgreSQL.")
    if database.url_override is None:
        return {
            "host": database.host,
            "port": database.port,
            "dbname": database.name,
            "user": database.username,
            "password": database.password.get_secret_value(),
            "sslmode": database.ssl_mode,
            "connect_timeout": 10,
        }
    url = make_url(database.url)
    if url.get_backend_name() != "postgresql":
        raise BackupError("Die Datenbankkonfiguration wird nicht unterstützt.")
    if set(url.query) - {"host", "port", "sslmode", "sslrootcert", "sslcert", "sslkey"}:
        raise BackupError("Die Datenbank-URL enthält nicht unterstützte Optionen.")
    return {
        "host": url.query.get("host", url.host or database.host),
        "port": url.query.get("port", url.port or database.port),
        "dbname": url.database or database.name,
        "user": url.username or database.username,
        "password": url.password
        if url.password is not None
        else database.password.get_secret_value(),
        "sslmode": url.query.get("sslmode", database.ssl_mode),
        "connect_timeout": 10,
        **{
            k: v
            for k, v in url.query.items()
            if k in ("sslrootcert", "sslcert", "sslkey")
        },
    }


@asynccontextmanager
async def operation_connection(
    database: DatabaseConfig, config: BackupConfig
) -> AsyncGenerator[AsyncConnection]:
    connection = await AsyncConnection.connect(
        **connection_parameters(database), autocommit=True
    )
    try:
        await connection.execute(
            "SELECT set_config('statement_timeout', %s, false)",
            (str(config.timeout_seconds * 1000),),
        )
        cursor = await connection.execute(
            "SELECT pg_try_advisory_lock(%s)", (OPERATION_LOCK,)
        )
        row = await cursor.fetchone()
        if not row or not row[0]:
            raise BackupError("Eine andere Sicherungsaktion läuft bereits.")
        yield connection
    finally:
        await connection.close()


async def acquire_maintenance(
    connection: AsyncConnection, config: BackupConfig
) -> None:
    await connection.execute(
        "SELECT set_config('statement_timeout', %s, false)",
        (str(config.lock_timeout_seconds * 1000),),
    )
    await connection.execute("SELECT pg_advisory_lock(%s)", (MAINTENANCE_LOCK,))
    await connection.execute(
        "SELECT set_config('statement_timeout', %s, false)",
        (str(config.timeout_seconds * 1000),),
    )


def client_environment(database: DatabaseConfig, directory: Path) -> dict[str, str]:
    parameters = connection_parameters(database)
    if any(
        any(character in str(value) for character in "\r\n\0")
        for value in parameters.values()
    ):
        raise BackupError("Die Datenbankverbindung enthält nicht unterstützte Zeichen.")

    # libpq escaping is different from shell quoting; never use a shell here.
    def escaped(value: Any) -> str:
        return str(value).replace("\\", "\\\\").replace(":", "\\:")

    password_file = directory / "pgpass"
    password_file.touch(mode=0o600)
    password_file.write_text(
        ":".join(
            escaped(parameters[k])
            for k in ("host", "port", "dbname", "user", "password")
        )
        + "\n"
    )
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PGPASSFILE": str(password_file),
        "PGCONNECT_TIMEOUT": "10",
        "PGAPPNAME": "alloq-backup",
    }
    for key, env_key in (
        ("host", "PGHOST"),
        ("port", "PGPORT"),
        ("dbname", "PGDATABASE"),
        ("user", "PGUSER"),
        ("sslmode", "PGSSLMODE"),
        ("sslrootcert", "PGSSLROOTCERT"),
        ("sslcert", "PGSSLCERT"),
        ("sslkey", "PGSSLKEY"),
    ):
        if key in parameters:
            environment[env_key] = str(parameters[key])
        elif env_key in os.environ:
            environment[env_key] = os.environ[env_key]
    return environment


async def run_client(
    name: str,
    arguments: list[str],
    environment: dict[str, str],
    config: BackupConfig,
    watched: Path | None = None,
) -> None:
    executable = shutil.which(name)
    if not executable:
        raise BackupError("Die PostgreSQL-Sicherungswerkzeuge sind nicht installiert.")
    process = await asyncio.create_subprocess_exec(
        executable,
        *arguments,
        env=environment,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE if watched else asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        async with asyncio.timeout(config.timeout_seconds):
            if watched and process.stdout is not None:
                size = 0
                async with await anyio.open_file(watched, "xb") as target:
                    await anyio.Path(watched).chmod(0o600)
                    while chunk := await process.stdout.read(1024 * 1024):
                        size += len(chunk)
                        if size > config.max_dump_bytes:
                            raise BackupError(
                                "Die Sicherung überschreitet die erlaubte Größe."
                            )
                        await target.write(chunk)
            await process.wait()
            if process.returncode:
                raise BackupError(
                    "Das PostgreSQL-Sicherungswerkzeug ist fehlgeschlagen."
                )
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def check_clients(server_major: int) -> dict[str, str]:
    """Use matching majors only; refuse implied upgrade/downgrade behaviour."""
    versions = {}
    for name in ("pg_dump", "pg_restore", "psql"):
        executable = shutil.which(name)
        if not executable:
            raise BackupError(
                "Die PostgreSQL-Sicherungswerkzeuge sind nicht installiert."
            )
        process = await asyncio.create_subprocess_exec(
            executable,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout=10)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        match = re.search(rb"PostgreSQL\) (\d+)", output)
        if process.returncode or not match or int(match[1]) != server_major:
            raise BackupError(
                "PostgreSQL-Server und Sicherungswerkzeuge benötigen "
                "dieselbe Hauptversion."
            )
        versions[name] = output.decode().strip()
    return versions


async def metadata(
    connection: AsyncConnection, database: DatabaseConfig
) -> dict[str, Any]:
    cursor = await connection.execute("SHOW server_version_num")
    row = await cursor.fetchone()
    major = int(row[0]) // 10000 if row else 0
    version_number = int(row[0]) if row else 0
    cursor = await connection.execute(
        "SELECT version_num FROM public.alembic_version ORDER BY version_num"
    )
    revisions = [row[0] for row in await cursor.fetchall()]
    cursor = await connection.execute(
        "SELECT extname, extversion FROM pg_extension ORDER BY extname"
    )
    extensions = [list(row) for row in await cursor.fetchall()]
    cursor = await connection.execute(TABLES)
    tables = []
    for schema, name in await cursor.fetchall():
        counted = await connection.execute(
            sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier(schema), sql.Identifier(name)
            )
        )
        count = await counted.fetchone()
        if count is None:
            raise BackupError("Die Datenbank konnte nicht geprüft werden.")
        tables.append([schema, name, count[0]])
    return {
        "server_major": major,
        "server_version_num": version_number,
        "revision": revisions,
        "key_id": hashlib.sha256(
            database.encryption_key.get_secret_value().encode()
        ).hexdigest(),
        "extensions": extensions,
        "tables": tables,
    }
