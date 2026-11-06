"""HTTP authorization, CSRF and bounded parsing protect every transfer route."""

import asyncio
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from reflex.compiler.compiler import compile_page

from appkit_user.authentication.backend.models import User

from app import backup_api
from app.database_backup.configuration import BackupConfig
from app.pages.backups import backup_forms

HEADERS = {"Origin": "https://app.example", "X-Alloq-Backup": "1"}


@pytest.fixture
def api_client() -> Iterator[tuple[FastAPI, AsyncMock]]:
    application = FastAPI()
    application.include_router(backup_api.router)
    config = SimpleNamespace(
        reflex=SimpleNamespace(deploy_url="https://app.example/alloq"),
        app=SimpleNamespace(database_backup=BackupConfig(enabled=True)),
    )
    auth = AsyncMock(
        return_value=User(
            id=1,
            email="admin@example.invalid",
            is_admin=True,
            roles=["database_backup"],
            is_verified=True,
        )
    )
    with (
        patch.object(backup_api, "configure", return_value=config),
        patch.object(backup_api, "require_session", auth),
    ):
        yield application, auth


@pytest.mark.parametrize("endpoint", ["export", "inspect", "import"])
@pytest.mark.parametrize(
    "headers", [{}, {"Origin": "https://evil.example", "X-Alloq-Backup": "1"}]
)
async def test_csrf_rejected_before_body_or_auth(
    api_client: tuple[FastAPI, AsyncMock], endpoint: str, headers: dict[str, str]
) -> None:
    application, auth = api_client
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="https://app.example"
    ) as client:
        response = await client.post(f"/api/admin/backups/{endpoint}", headers=headers)
    assert response.status_code == 403
    auth.assert_not_called()


@pytest.mark.parametrize("endpoint", ["export", "inspect", "import"])
@pytest.mark.parametrize(
    ("admin", "roles"), [(False, []), (True, []), (False, ["database_backup"])]
)
async def test_direct_routes_require_both_permissions(
    api_client: tuple[FastAPI, AsyncMock], endpoint: str, admin: bool, roles: list[str]
) -> None:
    application, auth = api_client
    auth.return_value = User(id=1, is_admin=admin, roles=roles, is_verified=True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="https://app.example"
    ) as client:
        response = await client.post(f"/api/admin/backups/{endpoint}", headers=HEADERS)
    assert response.status_code == 403


async def test_missing_signing_key_returns_safe_error(
    api_client: tuple[FastAPI, AsyncMock],
) -> None:
    application, _ = api_client
    backup_api.configure().app.database = SimpleNamespace()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="https://app.example"
    ) as client:
        response = await client.post("/api/admin/backups/export", headers=HEADERS)
    assert response.status_code == 400
    assert "Schlüssel" not in response.text  # secret values never appear


async def test_remote_plain_http_is_rejected_before_auth(
    api_client: tuple[FastAPI, AsyncMock],
) -> None:
    application, auth = api_client
    backup_api.configure().reflex.deploy_url = "http://app.example"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://app.example"
    ) as client:
        response = await client.post(
            "/api/admin/backups/export",
            headers={"Origin": "http://app.example", "X-Alloq-Backup": "1"},
        )
    assert response.status_code == 403
    auth.assert_not_called()


async def test_disabled_feature_fails_closed(
    api_client: tuple[FastAPI, AsyncMock],
) -> None:
    application, _ = api_client
    backup_api.configure().app.database_backup.enabled = False
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="https://app.example"
    ) as client:
        response = await client.post("/api/admin/backups/export", headers=HEADERS)
    assert response.status_code == 503


def test_credentials_are_uncontrolled_and_no_reflex_handlers_bound() -> None:
    rendered = str(backup_forms())
    assert "onChange" not in rendered
    assert "onSubmit" not in rendered
    assert "password_confirmed" not in rendered
    assert "data-backup-api" in rendered


def test_archive_input_values_never_persisted_by_script() -> None:
    source = Path("assets/js/database-backup.js").read_text()
    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert 'data.delete("password")' in source
    assert "textContent" in source
    assert "innerHTML" not in source


def test_native_backup_forms_compile_without_reflex_submit_handler() -> None:
    _, javascript = compile_page("backup-test", backup_forms())
    assert '"form"' in javascript
    assert "onSubmit" not in javascript
    assert "data-backup-api" in javascript


async def test_disconnect_cancels_in_progress_operation() -> None:
    request = SimpleNamespace(
        receive=AsyncMock(return_value={"type": "http.disconnect"})
    )
    stopped = asyncio.Event()

    async def operation() -> None:
        try:
            await asyncio.sleep(30)
        finally:
            stopped.set()

    from app.database_backup.configuration import BackupError  # noqa: PLC0415

    with pytest.raises(BackupError):
        await backup_api.while_connected(request, operation())
    assert stopped.is_set()
