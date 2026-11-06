"""Password-confirmed backup transfer. Secrets never enter Reflex events/state."""

import asyncio
import logging
import shutil
import sys
from collections.abc import AsyncGenerator, Awaitable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import anyio
from alloq_commons.access import can_manage_backups
from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection
from starlette.datastructures import FormData, UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import Request
from starlette.responses import FileResponse
from starlette.types import Receive, Scope, Send

from appkit_user.authentication.backend.models import User
from appkit_user.authentication.http_guard import require_session
from appkit_user.authentication.session_validation import session_cookie_name

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.configuration import configure
from app.database_backup.archive import CHUNK, digest_file
from app.database_backup.auth import (
    PasswordProof,
    current_user,
    verified_user,
    verify_password,
)
from app.database_backup.configuration import BackupError, validate_passphrase
from app.database_backup.postgres import operation_connection
from app.database_backup.service import BackupService
from app.database_backup.storage import private_workspace

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/backups")


def schema_revisions() -> list[str]:
    return sorted(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())


async def while_connected[T](request: Request, operation: Awaitable[T]) -> T:
    """Disconnects cancel native restore clients before they can commit."""

    async def disconnected() -> None:
        while True:
            message = await request.receive()
            if message["type"] == "http.disconnect":
                return

    task = asyncio.ensure_future(operation)
    monitor = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait(
            {task, monitor}, return_when=asyncio.FIRST_COMPLETED
        )
        if monitor in done and task not in done:
            raise BackupError("Die Sicherungsaktion wurde abgebrochen.")
        return await task
    finally:
        task.cancel()
        monitor.cancel()
        await asyncio.gather(task, monitor, return_exceptions=True)


async def require_backup_access(request: Request) -> User:
    config = configure()
    origin_url = urlsplit(config.reflex.deploy_url if config.reflex else "")
    allowed_origin = f"{origin_url.scheme}://{origin_url.netloc}"
    local = origin_url.hostname in ("localhost", "127.0.0.1", "::1")
    if not local and (origin_url.scheme != "https" or request.url.scheme != "https"):
        raise HTTPException(
            403, "Datenbanksicherungen benötigen eine HTTPS-Verbindung."
        )
    if (
        request.headers.get("origin") != allowed_origin
        or request.headers.get("x-alloq-backup") != "1"
    ):
        raise HTTPException(403, "Die Sicherungsanfrage ist nicht zulässig.")
    user = await require_session(request)
    if (
        not can_manage_backups(user)
        or user.needs_password_reset
        or not user.is_verified
    ):
        raise HTTPException(403, "Keine Berechtigung für Datenbanksicherungen.")
    if not config.app.database_backup.enabled:
        raise HTTPException(503, "Die Datenbanksicherung ist noch nicht konfiguriert.")
    return user


@dataclass
class Action:
    connection: AsyncConnection
    service: BackupService
    directory: Path
    session_id: str = dataclass_field(repr=False)
    proof: PasswordProof | None = dataclass_field(default=None, repr=False)


@asynccontextmanager
async def backup_action(request: Request, action: str) -> AsyncGenerator[Action]:
    config = configure()
    database = config.app.database
    if database is None:
        raise HTTPException(503, "Die Datenbank ist nicht konfiguriert.")
    operation_id = uuid4().hex
    user_id = 0
    try:
        config.app.database_backup.require_key()
        async with asyncio.timeout(config.app.database_backup.timeout_seconds):
            async with operation_connection(
                database, config.app.database_backup
            ) as connection:
                session_id = request.cookies.get(session_cookie_name(), "")
                user_id = (await current_user(connection, session_id))["id"]
                with private_workspace() as directory:
                    if await anyio.to_thread.run_sync(
                        lambda: shutil.disk_usage(directory).free
                    ) < (
                        3 * config.app.database_backup.max_dump_bytes
                        + 2 * config.app.database_backup.max_archive_bytes
                        + 67108864
                    ):
                        raise BackupError(
                            "Nicht genug temporärer Speicher für die Sicherung."
                        )
                    logger.info(
                        "Backup action=%s operation_id=%s actor_id=%s started",
                        action,
                        operation_id,
                        user_id,
                    )
                    yield Action(
                        connection,
                        BackupService(database, config.app.database_backup),
                        directory,
                        session_id,
                    )
        logger.info(
            "Backup action=%s operation_id=%s actor_id=%s completed",
            action,
            operation_id,
            user_id,
        )
    except BackupError as error:
        logger.warning(
            "Backup action=%s operation_id=%s actor_id=%s denied",
            action,
            operation_id,
            user_id,
        )
        raise HTTPException(400, str(error)) from None
    except (Exception, asyncio.CancelledError) as error:
        logger.warning(
            "Backup action=%s operation_id=%s actor_id=%s failed",
            action,
            operation_id,
            user_id,
        )
        if isinstance(error, asyncio.CancelledError):
            raise
        raise HTTPException(
            503,
            "Die Sicherungsaktion ist fehlgeschlagen.",
        ) from None


async def parse_form(request: Request, action: Action) -> FormData:
    total = 0
    limit = action.service.config.max_archive_bytes + 32768

    async def bounded_stream() -> AsyncGenerator[bytes]:
        nonlocal total
        async for chunk in request.stream():
            total += len(chunk)
            if total > limit:
                raise MultiPartException("Upload limit exceeded")
            yield chunk

    parser = MultiPartParser(
        request.headers, bounded_stream(), max_files=1, max_fields=6, max_part_size=4096
    )
    try:
        return await parser.parse()
    except BaseException as error:
        # Starlette closes spools on MultiPartException, but not cancellation.
        for spool in parser._files_to_close_on_error:  # noqa: SLF001
            spool.close()
        if isinstance(error, (MultiPartException, ValueError)):
            raise BackupError(
                "Die Sicherungsdatei oder Formulardaten sind ungültig oder zu groß."
            ) from None
        raise


def field(form: FormData, name: str) -> str:
    value = form.get(name)
    if not isinstance(value, str) or len(form.getlist(name)) != 1:
        raise BackupError("Die Sicherungsanfrage ist unvollständig.")
    return value


async def authenticate_form(form: FormData, action: Action) -> str:
    password, passphrase = field(form, "password"), field(form, "passphrase")
    action.proof = await verify_password(
        action.connection, action.session_id, password, action.service.config
    )
    validate_passphrase(passphrase)
    if password == passphrase:
        raise BackupError(
            "Sicherungspassphrase und Kontopasswort müssen verschieden sein."
        )
    return passphrase


async def save_upload(form: FormData, action: Action) -> str:
    upload = form.get("archive")
    if not isinstance(upload, UploadFile) or len(form.getlist("archive")) != 1:
        raise BackupError("Bitte wählen Sie eine Sicherungsdatei aus.")
    path = action.directory / "upload.zip"
    size = 0
    async with await anyio.open_file(path, "xb") as destination:
        while chunk := await upload.read(CHUNK):
            size += len(chunk)
            if size > action.service.config.max_archive_bytes:
                raise BackupError("Die Sicherungsdatei ist zu groß.")
            await destination.write(chunk)
    return await anyio.to_thread.run_sync(digest_file, path)


class BackupDownload(FileResponse):
    """Own resources through download/disconnect, including the operation lock."""

    def __init__(self, path: Path, stack: AsyncExitStack) -> None:
        super().__init__(
            path,
            media_type="application/zip",
            filename="alloq-backup.zip",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
        self.stack = stack

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async with self.stack:
            await super().__call__(scope, receive, send)


@router.post("/export", dependencies=[Depends(require_backup_access)])
async def export_backup(request: Request) -> FileResponse:
    stack = AsyncExitStack()
    try:
        action = await stack.enter_async_context(backup_action(request, "export"))
        form = await parse_form(request, action)
        try:
            passphrase = await authenticate_form(form, action)
            if field(form, "passphrase_confirmation") != passphrase:
                raise BackupError("Die Sicherungspassphrasen stimmen nicht überein.")
            archive = await while_connected(
                request,
                action.service.export_database(
                    action.connection,
                    action.directory,
                    passphrase,
                    configure().app.version,
                    schema_revisions(),
                ),
            )
            if action.proof is None:
                raise BackupError("Die Passwortbestätigung fehlt.")
            await verified_user(action.connection, action.session_id, action.proof)
        finally:
            await form.close()
        return BackupDownload(archive, stack.pop_all())
    except BaseException:
        await stack.__aexit__(*sys.exc_info())
        raise


@router.post("/inspect", dependencies=[Depends(require_backup_access)])
async def inspect_backup(request: Request) -> dict[str, Any]:
    async with backup_action(request, "inspect") as action:
        form = await parse_form(request, action)
        try:
            passphrase = await authenticate_form(form, action)
            checksum = await save_upload(form, action)
            manifest = await while_connected(
                request,
                action.service.inspect_archive(
                    action.connection, action.directory, passphrase, schema_revisions()
                ),
            )
            return {
                "created_at": manifest["created_at"],
                "app_version": manifest["app_version"],
                "revision": manifest["revision"],
                "sha256": checksum,
                "destination": action.service.database.name,
            }
        finally:
            await form.close()


@router.post("/import", dependencies=[Depends(require_backup_access)])
async def import_backup(request: Request) -> dict[str, str]:
    async with backup_action(request, "import") as action:
        form = await parse_form(request, action)
        try:
            passphrase = await authenticate_form(form, action)
            if field(form, "confirmation") != "DATENBANK ERSETZEN":
                raise BackupError("Bitte bestätigen Sie das Ersetzen der Datenbank.")
            checksum = await save_upload(form, action)
            if checksum != field(form, "sha256"):
                raise BackupError("Die Datei wurde seit der Prüfung geändert.")
            manifest = await while_connected(
                request,
                action.service.inspect_archive(
                    action.connection, action.directory, passphrase, schema_revisions()
                ),
            )
            if action.proof is None:
                raise BackupError("Die Passwortbestätigung fehlt.")
            await while_connected(
                request,
                action.service.restore_database(
                    action.connection,
                    action.directory,
                    manifest,
                    action.session_id,
                    action.proof,
                ),
            )
        finally:
            await form.close()
    return {"message": "Datenbank wiederhergestellt. Bitte melden Sie sich erneut an."}
