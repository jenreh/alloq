"""Orchestrate native backups without exposing credentials to reactive state."""

from pathlib import Path
from typing import Any

import anyio
from psycopg import AsyncConnection

from appkit_commons.database.configuration import DatabaseConfig

from .archive import read_archive, write_archive
from .auth import PasswordProof, verified_user
from .configuration import BackupConfig, BackupError
from .postgres import (
    check_clients,
    client_environment,
    metadata,
    run_client,
)
from .restore import (
    authorization_sql,
    cleanup_sql,
    deployment_grants,
    finalize_sql,
    transaction_script,
)


class BackupService:
    def __init__(self, database: DatabaseConfig, config: BackupConfig) -> None:
        self.database = database
        self.config = config

    async def export_database(
        self,
        connection: AsyncConnection,
        directory: Path,
        passphrase: str,
        app_version: str,
        revisions: list[str],
    ) -> Path:
        dump, archive = directory / "database.dump", directory / "backup.zip"
        environment = await anyio.to_thread.run_sync(
            client_environment, self.database, directory
        )
        async with connection.transaction():
            await connection.execute(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
            )
            manifest = await metadata(connection, self.database)
            if manifest["revision"] != revisions:
                raise BackupError(
                    "Die Datenbankschemaversion passt nicht zur Anwendung."
                )
            manifest["tool_versions"] = await check_clients(manifest["server_major"])
            manifest["app_version"] = app_version
            cursor = await connection.execute("SELECT pg_export_snapshot()")
            row = await cursor.fetchone()
            if row is None:
                raise BackupError("Die Datenbank konnte nicht geprüft werden.")
            await run_client(
                "pg_dump",
                [
                    "--format=custom",
                    "--no-owner",
                    "--no-acl",
                    "--no-tablespaces",
                    "--snapshot=" + row[0],
                ],
                environment,
                self.config,
                dump,
            )
        await anyio.to_thread.run_sync(
            write_archive, dump, archive, passphrase, manifest, self.config
        )
        return archive

    async def inspect_archive(
        self,
        connection: AsyncConnection,
        directory: Path,
        passphrase: str,
        revisions: list[str],
    ) -> dict[str, Any]:
        manifest = await anyio.to_thread.run_sync(
            read_archive,
            directory / "upload.zip",
            directory / "database.dump",
            passphrase,
            self.config,
        )
        live = await metadata(connection, self.database)
        if any(
            manifest.get(key) != live[key]
            for key in ("server_major", "key_id", "extensions")
        ):
            raise BackupError(
                "PostgreSQL-Version, Erweiterungen oder "
                "Verschlüsselungsschlüssel passen nicht."
            )
        if manifest.get("revision") != revisions or live["revision"] != revisions:
            raise BackupError("Die Datenbankschemaversion passt nicht zur Anwendung.")
        await check_clients(live["server_major"])
        return manifest

    async def restore_database(
        self,
        connection: AsyncConnection,
        directory: Path,
        manifest: dict[str, Any],
        session_id: str,
        proof: PasswordProof,
    ) -> None:
        environment = await anyio.to_thread.run_sync(
            client_environment, self.database, directory
        )
        restored = directory / "restore.sql"
        await run_client(
            "pg_restore",
            [
                "--file=-",
                "--single-transaction",
                "--no-owner",
                "--no-acl",
                "--no-tablespaces",
                str(directory / "database.dump"),
            ],
            environment,
            self.config,
            restored,
        )
        user = await verified_user(connection, session_id, proof)
        cleanup = authorization_sql(
            user,
            session_id,
            self.config.timeout_seconds,
            self.config.lock_timeout_seconds,
        )
        cleanup += await cleanup_sql(connection)
        grants = await deployment_grants(connection)
        final = finalize_sql(manifest, grants)
        script = await anyio.to_thread.run_sync(
            transaction_script, directory, cleanup, final, self.config.max_dump_bytes
        )
        await run_client(
            "psql",
            [
                "--no-psqlrc",
                "--no-password",
                "--set=ON_ERROR_STOP=1",
                "--file=" + str(script),
            ],
            environment,
            self.config,
        )
