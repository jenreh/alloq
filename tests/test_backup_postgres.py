"""Real disposable PostgreSQL proves replacement, rollback and cross-worker locks."""

import asyncio
import logging
import secrets
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import psycopg
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from psycopg import sql
from pydantic import SecretStr
from sqlalchemy import URL, create_engine, text

from appkit_commons.database.configuration import DatabaseConfig
from appkit_commons.security import generate_password_hash
from appkit_user.authentication.backend.models import User

from app import backup_api
from app.database_backup import runtime
from app.database_backup import service as service_module
from app.database_backup.auth import verify_password
from app.database_backup.configuration import BackupConfig, BackupError
from app.database_backup.maintenance import MAINTENANCE_LOCK, install_maintenance_guard
from app.database_backup.postgres import connection_parameters, operation_connection
from app.database_backup.service import BackupService

PHRASE = secrets.token_urlsafe(24)
ACCOUNT_PASSWORD = secrets.token_urlsafe(24)
SESSION = secrets.token_urlsafe(32)


@pytest.fixture(scope="module")
def postgres_database(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[DatabaseConfig]:
    initdb, pg_ctl = shutil.which("initdb"), shutil.which("pg_ctl")
    if not initdb or not pg_ctl:
        pytest.skip("Disposable PostgreSQL requires initdb and pg_ctl")
    directory = tmp_path_factory.mktemp("backup-pg")
    directory.chmod(0o700)
    data = directory / "data"
    # A short private Unix socket path avoids TCP and any existing local database.
    socket = Path(tempfile.mkdtemp(prefix="alloq-pg-", dir="/private/tmp"))
    subprocess.run(  # noqa: S603 - installed PostgreSQL executable, private fixture
        [initdb, "-D", str(data), "--auth=trust", "--no-locale", "--encoding=UTF8"],
        check=True,
        capture_output=True,
    )
    subprocess.run(  # noqa: S603 - private disposable database, no external target
        [
            pg_ctl,
            "-D",
            str(data),
            "-l",
            str(directory / "server.log"),
            "-o",
            f"-k {socket} -h ''",
            "-w",
            "start",
        ],
        check=True,
        capture_output=True,
    )
    try:
        with psycopg.connect(
            host=str(socket), dbname="postgres", autocommit=True
        ) as admin:
            admin.execute(
                "CREATE ROLE backup_test LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE"
            )
            admin.execute("CREATE DATABASE backup_test OWNER backup_test")
        yield DatabaseConfig(
            host=str(socket),
            port=5432,
            name="backup_test",
            username="backup_test",
            password=SecretStr(""),
            encryption_key=SecretStr(Fernet.generate_key().decode()),
            ssl_mode="disable",
            type="postgresql",
            url_override=URL.create(
                "postgresql+psycopg",
                username="backup_test",
                database="backup_test",
                query={"host": str(socket)},
            ).render_as_string(hide_password=False),
        )
    finally:
        subprocess.run(  # noqa: S603 - stops only this fixture's private cluster
            [pg_ctl, "-D", str(data), "-m", "immediate", "-w", "stop"],
            check=True,
            capture_output=True,
        )
        shutil.rmtree(socket)


@pytest.fixture
def prepared_database(postgres_database: DatabaseConfig) -> DatabaseConfig:
    with psycopg.connect(
        **connection_parameters(postgres_database), autocommit=True
    ) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        conn.execute("CREATE TABLE alembic_version (version_num varchar PRIMARY KEY)")
        conn.execute("INSERT INTO alembic_version VALUES ('test-head')")
        conn.execute(
            "CREATE TABLE records (id serial PRIMARY KEY, value text, payload bytea)"
        )
        conn.execute(
            "INSERT INTO records (value,payload) VALUES ('original', %s)",
            (b"\x00\xff",),
        )
        conn.execute("ALTER TABLE records ADD secret text, ADD large_oid oid")
        cipher = Fernet(postgres_database.encryption_key.get_secret_value())
        conn.execute(
            "UPDATE records SET secret=%s, large_oid=lo_from_bytea(0,%s)",
            (cipher.encrypt(b"private-field").decode(), b"large-object-data"),
        )
        conn.execute(
            "CREATE TABLE auth_users (id int PRIMARY KEY, email text, _password text, "
            "is_admin bool, is_active bool, is_verified bool, "
            "needs_password_reset bool, roles text[])"
        )
        conn.execute(
            "INSERT INTO auth_users VALUES "
            "(1,'test@example.invalid',%s,true,true,true,false,ARRAY['database_backup'])",
            (generate_password_hash(ACCOUNT_PASSWORD),),
        )
        conn.execute(
            "CREATE TABLE auth_sessions "
            "(session_id text, user_id int, expires_at timestamptz)"
        )
        conn.execute(
            "INSERT INTO auth_sessions VALUES (%s,1,now()+interval '1 hour')",
            (SESSION,),
        )
        for table in (
            "auth_oauth_states",
            "auth_password_reset_tokens",
            "auth_password_reset_requests",
        ):
            conn.execute(
                sql.SQL("CREATE TABLE {} (token text)").format(sql.Identifier(table))
            )
            conn.execute(
                sql.SQL("INSERT INTO {} VALUES ('old-token')").format(
                    sql.Identifier(table)
                )
            )
        conn.execute(
            "CREATE TABLE auth_login_throttle "
            "(key text PRIMARY KEY, failures int, window_started_at timestamptz)"
        )
    return postgres_database


def _service(database: DatabaseConfig) -> BackupService:
    return BackupService(
        database,
        BackupConfig(
            enabled=True, signing_key=SecretStr("integration-signing-key-" + "x" * 40)
        ),
    )


async def _export(service: BackupService, directory: Path) -> Path:
    async with operation_connection(service.database, service.config) as connection:
        await verify_password(connection, SESSION, ACCOUNT_PASSWORD, service.config)
        return await service.export_database(
            connection, directory, PHRASE, "test", ["test-head"]
        )


async def test_full_round_trip_and_extra_objects_removed(
    prepared_database: DatabaseConfig, tmp_path: Path
) -> None:
    service = _service(prepared_database)
    source = tmp_path / "source"
    source.mkdir()
    archive = await _export(service, source)
    with psycopg.connect(
        **connection_parameters(prepared_database), autocommit=True
    ) as conn:
        conn.execute(
            "UPDATE records SET value='changed'; CREATE TABLE obsolete (id int)"
        )
    destination = tmp_path / "destination"
    destination.mkdir()
    shutil.copyfile(archive, destination / "upload.zip")
    async with operation_connection(prepared_database, service.config) as connection:
        manifest = await service.inspect_archive(
            connection, destination, PHRASE, ["test-head"]
        )
        await service.restore_database(
            connection,
            destination,
            manifest,
            SESSION,
            await verify_password(
                connection, SESSION, ACCOUNT_PASSWORD, service.config
            ),
        )
    with psycopg.connect(**connection_parameters(prepared_database)) as conn:
        assert conn.execute("SELECT value,payload FROM records").fetchone() == (
            "original",
            b"\x00\xff",
        )
        assert conn.execute("SELECT to_regclass('public.obsolete')").fetchone() == (
            None,
        )
        assert conn.execute("SELECT count(*) FROM auth_sessions").fetchone() == (0,)
        assert conn.execute(
            "SELECT count(*) FROM auth_password_reset_tokens"
        ).fetchone() == (0,)
        assert conn.execute(
            "INSERT INTO records(value) VALUES ('next') RETURNING id"
        ).fetchone() == (2,)
        encrypted = conn.execute(
            "SELECT secret,lo_get(large_oid) FROM records WHERE id=1"
        ).fetchone()
        assert encrypted is not None
        assert (
            Fernet(prepared_database.encryption_key.get_secret_value()).decrypt(
                encrypted[0]
            )
            == b"private-field"
        )
        assert encrypted[1] == b"large-object-data"


async def test_validation_failure_rolls_back_cleanup_and_restore(
    prepared_database: DatabaseConfig, tmp_path: Path
) -> None:
    service = _service(prepared_database)
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    archive = await _export(service, source)
    shutil.copyfile(archive, target / "upload.zip")
    with psycopg.connect(
        **connection_parameters(prepared_database), autocommit=True
    ) as conn:
        conn.execute(
            "UPDATE records SET value='keep-me'; CREATE TABLE obsolete (id int)"
        )
    async with operation_connection(prepared_database, service.config) as connection:
        manifest = await service.inspect_archive(
            connection, target, PHRASE, ["test-head"]
        )
        manifest["tables"].append(["public", "missing_table", 1])
        with pytest.raises(BackupError):
            await service.restore_database(
                connection,
                target,
                manifest,
                SESSION,
                await verify_password(
                    connection, SESSION, ACCOUNT_PASSWORD, service.config
                ),
            )
    with psycopg.connect(**connection_parameters(prepared_database)) as conn:
        assert conn.execute("SELECT value FROM records").fetchone() == ("keep-me",)
        assert conn.execute("SELECT to_regclass('public.obsolete')").fetchone() == (
            "obsolete",
        )
        assert conn.execute("SELECT count(*) FROM auth_sessions").fetchone() == (1,)


async def test_password_failure_counter_survives_and_locks(
    prepared_database: DatabaseConfig,
) -> None:
    service = _service(prepared_database)
    async with operation_connection(prepared_database, service.config) as connection:
        for _ in range(service.config.max_password_attempts):
            with pytest.raises(BackupError):
                await verify_password(connection, SESSION, "wrong", service.config)
        with pytest.raises(BackupError):
            await verify_password(connection, SESSION, ACCOUNT_PASSWORD, service.config)


async def test_maintenance_blocks_other_application_workers(
    prepared_database: DatabaseConfig,
) -> None:
    from app.database_backup.postgres import acquire_maintenance  # noqa: PLC0415

    service = _service(prepared_database)
    install_maintenance_guard()
    async with operation_connection(prepared_database, service.config) as connection:
        await acquire_maintenance(connection, service.config)
        engine = create_engine(prepared_database.url)
        try:
            with engine.connect() as application, pytest.raises(BackupError):
                application.execute(text("SELECT 1"))
        finally:
            engine.dispose()


async def test_concurrent_operation_rejected(prepared_database: DatabaseConfig) -> None:
    service = _service(prepared_database)
    async with operation_connection(prepared_database, service.config):
        with pytest.raises(BackupError):
            async with operation_connection(prepared_database, service.config):
                pytest.fail("overlapping backup must not acquire the operation lock")


@pytest.mark.parametrize(
    "change",
    [
        "is_active=false",
        "is_admin=false",
        "is_verified=false",
        "needs_password_reset=true",
        "roles=ARRAY[]::text[]",
        "_password=NULL",
    ],
)
async def test_account_status_and_sso_only_accounts_blocked(
    prepared_database: DatabaseConfig, change: str
) -> None:
    with psycopg.connect(
        **connection_parameters(prepared_database), autocommit=True
    ) as conn:
        conn.execute(sql.SQL("UPDATE auth_users SET " + change))  # noqa: S608 - fixed test cases
    service = _service(prepared_database)
    async with operation_connection(prepared_database, service.config) as connection:
        with pytest.raises(BackupError):
            await verify_password(connection, SESSION, ACCOUNT_PASSWORD, service.config)


async def test_quoted_identifiers_grants_and_default_privileges_round_trip(
    prepared_database: DatabaseConfig, tmp_path: Path
) -> None:
    service = _service(prepared_database)
    schema, table = "quote$checks$schema'", "table$grant$'"
    with psycopg.connect(
        **connection_parameters(prepared_database), autocommit=True
    ) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        qualified = sql.SQL("{}.{}").format(
            sql.Identifier(schema), sql.Identifier(table)
        )
        conn.execute(sql.SQL("CREATE TABLE {} (value text)").format(qualified))
        conn.execute(sql.SQL("INSERT INTO {} VALUES ('quoted')").format(qualified))
        conn.execute(sql.SQL("GRANT SELECT ON {} TO PUBLIC").format(qualified))
        conn.execute(
            "CREATE FUNCTION public.private_function() RETURNS int "
            "LANGUAGE sql AS 'SELECT 1'"
        )
        conn.execute("REVOKE ALL ON FUNCTION public.private_function() FROM PUBLIC")
        conn.execute("CREATE TYPE public.private_status AS ENUM ('safe')")
        conn.execute("REVOKE ALL ON TYPE public.private_status FROM PUBLIC")
        conn.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO PUBLIC"
        )
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    archive = await _export(service, source)
    shutil.copyfile(archive, target / "upload.zip")
    async with operation_connection(prepared_database, service.config) as connection:
        manifest = await service.inspect_archive(
            connection, target, PHRASE, ["test-head"]
        )
        await service.restore_database(
            connection,
            target,
            manifest,
            SESSION,
            await verify_password(
                connection, SESSION, ACCOUNT_PASSWORD, service.config
            ),
        )
    with psycopg.connect(
        **connection_parameters(prepared_database), autocommit=True
    ) as conn:
        assert conn.execute(
            sql.SQL("SELECT value FROM {}.{}").format(
                sql.Identifier(schema), sql.Identifier(table)
            )
        ).fetchone() == ("quoted",)
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        assert conn.execute(
            "SELECT count(*) FROM pg_proc p CROSS JOIN LATERAL aclexplode(p.proacl) a "
            "WHERE p.oid='public.private_function()'::regprocedure AND a.grantee=0"
        ).fetchone() == (0,)
        conn.execute("CREATE TABLE public.future_table (id int)")
        assert conn.execute(
            "SELECT count(*) FROM pg_type t CROSS JOIN LATERAL aclexplode(t.typacl) a "
            "WHERE t.oid='public.private_status'::regtype AND a.grantee=0"
        ).fetchone() == (0,)
        assert conn.execute(
            "SELECT count(*) FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a "
            "WHERE c.oid='public.future_table'::regclass AND a.grantee=0 "
            "AND a.privilege_type='SELECT'"
        ).fetchone() == (1,)


async def test_http_export_inspect_and_confirmed_import(
    prepared_database: DatabaseConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = _service(prepared_database)
    application = FastAPI()
    application.include_router(backup_api.router)
    config = SimpleNamespace(
        reflex=SimpleNamespace(deploy_url="https://app.example"),
        app=SimpleNamespace(
            database=prepared_database, database_backup=service.config, version="test"
        ),
    )
    headers = {"Origin": "https://app.example", "X-Alloq-Backup": "1"}
    actor = User(id=1, is_admin=True, is_verified=True, roles=["database_backup"])
    with (
        patch.object(backup_api, "configure", return_value=config),
        patch.object(backup_api, "require_session", AsyncMock(return_value=actor)),
        patch.object(backup_api, "session_cookie_name", return_value="test-session"),
        patch.object(backup_api, "schema_revisions", return_value=["test-head"]),
        caplog.at_level(logging.INFO),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url="https://app.example",
            cookies={"test-session": SESSION},
            headers=headers,
        ) as client:
            export = await client.post(
                "/api/admin/backups/export",
                files={
                    "password": (None, ACCOUNT_PASSWORD),
                    "passphrase": (None, PHRASE),
                    "passphrase_confirmation": (None, PHRASE),
                },
            )
            assert export.status_code == 200, export.text
            assert export.headers["cache-control"] == "no-store"
            assert b"private-field" not in export.content
            upload = {"archive": ("backup.zip", export.content, "application/zip")}
            form = {"password": ACCOUNT_PASSWORD, "passphrase": PHRASE}
            inspected = await client.post(
                "/api/admin/backups/inspect", files=upload, data=form
            )
            assert inspected.status_code == 200, inspected.text
            form["sha256"] = inspected.json()["sha256"]
            form["confirmation"] = "DATENBANK ERSETZEN"
            imported = await client.post(
                "/api/admin/backups/import", files=upload, data=form
            )
            assert imported.status_code == 200, imported.text
            stale = await client.post(
                "/api/admin/backups/export",
                files={
                    "password": (None, ACCOUNT_PASSWORD),
                    "passphrase": (None, PHRASE),
                    "passphrase_confirmation": (None, PHRASE),
                },
            )
            assert stale.status_code == 400
    assert ACCOUNT_PASSWORD not in caplog.text
    assert PHRASE not in caplog.text
    assert SESSION not in caplog.text


async def _wait_for_restore(database: DatabaseConfig, *, waiting: bool) -> int:
    async with await psycopg.AsyncConnection.connect(
        **connection_parameters(database), autocommit=True
    ) as observer:
        for _ in range(250):
            cursor = await observer.execute(
                "SELECT l.pid FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid "
                "WHERE a.application_name='alloq-backup' AND l.locktype='advisory' "
                "AND l.classid=%s AND l.objid=%s AND l.mode='ExclusiveLock' "
                "AND l.granted=%s",
                (MAINTENANCE_LOCK >> 32, MAINTENANCE_LOCK & 0xFFFFFFFF, not waiting),
            )
            row = await cursor.fetchone()
            if row:
                return row[0]
            await asyncio.sleep(0.02)
    pytest.fail("Restore did not reach its expected maintenance lock state")


async def test_cancellation_rolls_back_and_child_transaction_owns_lock(
    prepared_database: DatabaseConfig,
    tmp_path: Path,
) -> None:
    service = _service(prepared_database)
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    archive = await _export(service, source)
    shutil.copyfile(archive, target / "upload.zip")
    with psycopg.connect(
        **connection_parameters(prepared_database), autocommit=True
    ) as conn:
        conn.execute("UPDATE records SET value='keep-on-cancel'")
    original_final = service_module.finalize_sql
    async with operation_connection(prepared_database, service.config) as connection:
        manifest = await service.inspect_archive(
            connection, target, PHRASE, ["test-head"]
        )
        proof = await verify_password(
            connection, SESSION, ACCOUNT_PASSWORD, service.config
        )
        with patch.object(
            service_module,
            "finalize_sql",
            side_effect=lambda m, g: "SELECT pg_sleep(30);\n" + original_final(m, g),
        ):
            task = asyncio.create_task(
                service.restore_database(connection, target, manifest, SESSION, proof)
            )
            child_pid = await _wait_for_restore(prepared_database, waiting=False)
            assert child_pid != connection.info.backend_pid
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    with psycopg.connect(**connection_parameters(prepared_database)) as conn:
        assert conn.execute("SELECT value FROM records").fetchone() == (
            "keep-on-cancel",
        )
        assert conn.execute("SELECT count(*) FROM auth_sessions").fetchone() == (1,)


async def test_restore_drains_complete_activity_and_blocks_new_events(
    prepared_database: DatabaseConfig,
    tmp_path: Path,
) -> None:
    service = _service(prepared_database)
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    archive = await _export(service, source)
    shutil.copyfile(archive, target / "upload.zip")
    registry = SimpleNamespace(get=lambda _kind: prepared_database)
    with patch.object(runtime, "service_registry", return_value=registry):
        runtime.activity_pool.cache_clear()
        try:
            async with operation_connection(
                prepared_database, service.config
            ) as connection:
                manifest = await service.inspect_archive(
                    connection, target, PHRASE, ["test-head"]
                )
                proof = await verify_password(
                    connection, SESSION, ACCOUNT_PASSWORD, service.config
                )
                async with runtime.application_activity():
                    task = asyncio.create_task(
                        service.restore_database(
                            connection, target, manifest, SESSION, proof
                        )
                    )
                    await _wait_for_restore(prepared_database, waiting=True)
                    assert not task.done()
                    with pytest.raises(BackupError):
                        async with runtime.application_activity():
                            pytest.fail("New events must not jump a waiting restore")
                await task
        finally:
            await runtime.activity_pool().close()
            runtime.activity_pool.cache_clear()


async def test_password_change_invalidates_operation_proof(
    prepared_database: DatabaseConfig,
) -> None:
    from app.database_backup.auth import verified_user  # noqa: PLC0415

    service = _service(prepared_database)
    async with operation_connection(prepared_database, service.config) as connection:
        proof = await verify_password(
            connection, SESSION, ACCOUNT_PASSWORD, service.config
        )
        await connection.execute(
            "UPDATE auth_users SET _password=%s",
            (generate_password_hash(secrets.token_urlsafe(24)),),
        )
        with pytest.raises(BackupError):
            await verified_user(connection, SESSION, proof)
