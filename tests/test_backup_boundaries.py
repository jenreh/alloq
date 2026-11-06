"""Reject unsafe inputs and failed native operations before they touch a database."""

import asyncio
import io
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr
from starlette.datastructures import FormData, UploadFile
from starlette.requests import Request

from appkit_commons.database.configuration import DatabaseConfig

from app import backup_api
from app.database_backup.auth import PasswordProof
from app.database_backup.configuration import BackupConfig, BackupError
from app.database_backup.postgres import (
    check_clients,
    client_environment,
    connection_parameters,
    run_client,
)
from app.database_backup.restore import transaction_script


@pytest.mark.parametrize(
    "data",
    [
        FormData(),
        FormData([("password", "a"), ("password", "b")]),
        FormData({"password": UploadFile(io.BytesIO())}),
    ],
)
def test_missing_duplicate_or_file_credential_field_rejected(data: FormData) -> None:
    with pytest.raises(BackupError):
        backup_api.field(data, "password")


async def test_same_account_and_archive_password_rejected() -> None:
    phrase = "a-separate-long-passphrase-with-variety"
    action = backup_api.Action(
        None, SimpleNamespace(config=BackupConfig()), Path("unused"), "session"
    )
    form = FormData({"password": phrase, "passphrase": phrase})
    with (
        patch.object(
            backup_api,
            "verify_password",
            AsyncMock(return_value=PasswordProof(1, "hash")),
        ),
        pytest.raises(BackupError, match="verschieden"),
    ):
        await backup_api.authenticate_form(form, action)


async def test_body_limit_rejected_while_streaming(tmp_path: Path) -> None:
    config = BackupConfig(max_archive_bytes=1024)
    action = backup_api.Action(
        None, SimpleNamespace(config=config), tmp_path, "session"
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"content-type", b"multipart/form-data; boundary=backup")],
        },
        receive=AsyncMock(
            return_value={
                "type": "http.request",
                "body": b"x" * 40000,
                "more_body": False,
            }
        ),
    )
    with pytest.raises(BackupError):
        await backup_api.parse_form(request, action)


async def test_upload_size_limit_and_missing_file(tmp_path: Path) -> None:
    config = BackupConfig(max_archive_bytes=1024)
    action = backup_api.Action(
        None, SimpleNamespace(config=config), tmp_path, "session"
    )
    with pytest.raises(BackupError):
        await backup_api.save_upload(FormData(), action)
    form = FormData({"archive": UploadFile(io.BytesIO(b"x" * 4096))})
    try:
        with pytest.raises(BackupError):
            await backup_api.save_upload(form, action)
    finally:
        await form.close()


def test_credentials_stay_out_of_client_environment_and_are_private(
    tmp_path: Path,
) -> None:
    password = SecretStr("a:test\\value")
    database = DatabaseConfig(password=password)
    environment = client_environment(database, tmp_path)
    assert "PGPASSWORD" not in environment
    assert password.get_secret_value() not in repr(environment)
    assert (tmp_path / "pgpass").stat().st_mode & 0o777 == 0o600
    assert "a\\:test\\\\value" in (tmp_path / "pgpass").read_text()


def test_newlines_cannot_inject_another_pgpass_entry(tmp_path: Path) -> None:
    database = DatabaseConfig(password=SecretStr("bad\nextra-entry"))
    with pytest.raises(BackupError):
        client_environment(database, tmp_path)


@pytest.mark.parametrize(
    "database",
    [
        DatabaseConfig(type="sqlite"),
        DatabaseConfig(url_override="sqlite:///:memory:"),
        DatabaseConfig(url_override="postgresql://user@host/db?options=unsafe"),
    ],
)
def test_unsupported_database_or_connection_options_fail_closed(
    database: DatabaseConfig,
) -> None:
    with pytest.raises(BackupError):
        connection_parameters(database)


async def test_missing_clients_fail_closed() -> None:
    with patch("app.database_backup.postgres.shutil.which", return_value=None):
        with pytest.raises(BackupError):
            await check_clients(16)
        with pytest.raises(BackupError):
            await run_client("pg_dump", [], {}, BackupConfig())


async def test_native_output_is_bounded_before_writing(tmp_path: Path) -> None:
    output = tmp_path / "dump"
    with pytest.raises(BackupError):
        await run_client(
            sys.executable,
            ["-c", "import sys; sys.stdout.write('x'*8192)"],
            {},
            BackupConfig(max_dump_bytes=1024),
            output,
        )
    assert output.stat().st_size <= 1024


async def test_native_timeout_cancels_child() -> None:
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.1):
            await run_client(
                sys.executable,
                ["-c", "import time; time.sleep(30)"],
                {},
                BackupConfig(),
            )


@pytest.mark.parametrize("script", [b"SELECT 1;", b"\nBEGIN;\nSELECT 1;"])
def test_invalid_native_transaction_script_rejected(
    tmp_path: Path, script: bytes
) -> None:
    (tmp_path / "restore.sql").write_bytes(script)
    with pytest.raises(BackupError):
        transaction_script(tmp_path, "SELECT 2;", "SELECT 3;", 4096)


def test_copy_row_named_commit_is_not_modified(tmp_path: Path) -> None:
    original = (
        b"\nBEGIN;\nSET statement_timeout = 0;\nSET row_security = off;\n"
        b"COPY t FROM stdin;\nCOMMIT;\n\\.\n\nCOMMIT;\n"
    )
    (tmp_path / "restore.sql").write_bytes(original)
    result = transaction_script(
        tmp_path, "SELECT 'before';\n", "SELECT 'after';\n", 4096
    ).read_bytes()
    assert b"COPY t FROM stdin;\nCOMMIT;\n\\." in result
    assert result.index(b"SELECT 'before'") < result.index(b"COPY t")
    assert result.index(b"SET statement_timeout = 0") < result.index(b"SELECT 'before'")
    assert result.index(b"SELECT 'after'") > result.index(b"\\.")
