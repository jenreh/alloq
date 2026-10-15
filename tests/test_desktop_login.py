"""Desktop sign-in flow, schema check, profile and build script."""

import importlib.util
import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Self
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import rxconfig

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.desktop import login_state, profile, schema
from app.desktop.entra import Account, SignInError
from app.desktop.login_state import DesktopLoginState, microsoft_account

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = Account(email="ada@example.com", name="Ada", db_user="ada@example.com")


class TestSchema:
    def test_known_revisions_are_the_alembic_history(self) -> None:
        scripts = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
        history = tuple(r.revision for r in scripts.walk_revisions())
        assert history == schema.KNOWN_REVISIONS
        assert scripts.get_current_head() == schema.EXPECTED_REVISION

    @pytest.mark.asyncio
    async def test_matching_schema(self) -> None:
        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: schema.EXPECTED_REVISION)
        )
        assert await schema.schema_problem(session) is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("current", "hint"),
        [
            (schema.KNOWN_REVISIONS[-1], "Migration"),
            ("unknown-newer", "App aktualisieren"),
            (None, "unbekannt"),
        ],
    )
    async def test_mismatch_says_which_side_is_behind(
        self, current: str | None, hint: str
    ) -> None:
        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: current)
        )
        problem = await schema.schema_problem(session)
        assert problem is not None
        assert hint in problem


class TestMicrosoftAccount:
    @pytest.mark.asyncio
    async def test_cached_account_skips_the_browser(self) -> None:
        sign_in = MagicMock()
        sign_in.sign_in_silently.return_value = ACCOUNT
        assert await microsoft_account(sign_in) == ACCOUNT
        sign_in.sign_in_interactively.assert_not_called()

    @pytest.mark.asyncio
    async def test_browser_when_nothing_is_cached(self) -> None:
        sign_in = MagicMock()
        sign_in.sign_in_silently.return_value = None
        sign_in.sign_in_interactively.return_value = ACCOUNT
        assert await microsoft_account(sign_in) == ACCOUNT


class _Proxy:
    """Minimal background-task proxy: `async with self` around a plain object."""

    def __init__(self) -> None:
        self.is_loading = False
        self.error_message = ""
        self.redirect_to = "/plan"
        self.homepage = "/"
        self.created: list[Any] = []
        self.events: list[Any] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def _prepare_login(self) -> str:
        return self.redirect_to

    async def _create_session(self, _db: Any, user: Any) -> None:
        self.created.append(user)


def _session_ctx() -> Any:
    @asynccontextmanager
    async def _ctx() -> Any:
        yield MagicMock()

    return _ctx


def _account_mock(account: Any) -> AsyncMock:
    if isinstance(account, Exception):
        return AsyncMock(side_effect=account)
    return AsyncMock(return_value=account)


async def _run_sign_in(
    *, user: Any, problem: str | None = None, account: Any = ACCOUNT
) -> _Proxy:
    proxy = _Proxy()
    handler = DesktopLoginState.sign_in_with_microsoft.fn  # ty: ignore[unresolved-attribute]
    finder = AsyncMock(return_value=user)
    with (
        patch.object(login_state, "get_sign_in", return_value=MagicMock()),
        patch.object(login_state, "microsoft_account", _account_mock(account)),
        patch.object(login_state, "reset_connections", AsyncMock()),
        patch.object(login_state, "get_asyncdb_session", _session_ctx()),
        patch.object(login_state, "schema_problem", AsyncMock(return_value=problem)),
        patch.object(login_state, "find_user", finder),
    ):
        async for event in handler(proxy):
            proxy.events.append(event)
    return proxy


class TestSignInFlow:
    @pytest.mark.asyncio
    async def test_opens_the_alloq_session(self) -> None:
        user = SimpleNamespace(id=5, is_active=True, is_verified=True)
        proxy = await _run_sign_in(user=user)
        assert proxy.created == [user]
        assert proxy.error_message == ""
        assert proxy.is_loading is False
        assert proxy.redirect_to == ""
        assert any("/plan" in repr(event) for event in proxy.events)

    @pytest.mark.asyncio
    async def test_unknown_user(self) -> None:
        proxy = await _run_sign_in(user=None)
        assert "kein alloq-Konto" in proxy.error_message
        assert proxy.created == []

    @pytest.mark.asyncio
    async def test_inactive_user(self) -> None:
        user = SimpleNamespace(id=5, is_active=False, is_verified=True)
        proxy = await _run_sign_in(user=user)
        assert "deaktiviert" in proxy.error_message

    @pytest.mark.asyncio
    async def test_schema_mismatch_stops_sign_in(self) -> None:
        user = SimpleNamespace(id=5, is_active=True, is_verified=True)
        proxy = await _run_sign_in(user=user, problem="Bitte aktualisieren")
        assert proxy.error_message == "Bitte aktualisieren"
        assert proxy.created == []

    @pytest.mark.asyncio
    async def test_fake_sign_in_tolerates_older_schema(self) -> None:
        user = SimpleNamespace(id=5, is_active=True, is_verified=True)
        with patch.object(login_state, "fake_email", return_value="a@b.c"):
            proxy = await _run_sign_in(user=user, problem="älter")
        assert proxy.created == [user]

    @pytest.mark.asyncio
    async def test_microsoft_error_is_shown(self) -> None:
        proxy = await _run_sign_in(user=None, account=SignInError("abgebrochen"))
        assert proxy.error_message == "abgebrochen"

    @pytest.mark.asyncio
    async def test_unexpected_error(self) -> None:
        proxy = await _run_sign_in(user=None, account=RuntimeError("boom"))
        assert proxy.error_message == login_state.FAILED


class TestSignOut:
    @pytest.mark.asyncio
    async def test_forgets_account_and_connections(self) -> None:
        state = MagicMock()
        state.logout = AsyncMock(return_value=["redirect"])
        sign_in = MagicMock()
        reset = AsyncMock()
        handler = DesktopLoginState.sign_out.fn  # ty: ignore[unresolved-attribute]
        with (
            patch.object(login_state, "get_sign_in", return_value=sign_in),
            patch.object(login_state, "reset_connections", reset),
        ):
            events = await handler(state)
        assert events == ["redirect"]
        sign_in.sign_out.assert_called_once()
        reset.assert_awaited_once()


class TestResetConnections:
    @pytest.mark.asyncio
    async def test_closes_pools(self) -> None:
        manager = MagicMock()
        manager.close = AsyncMock()
        with patch.object(
            login_state, "get_async_session_manager", return_value=manager
        ):
            await login_state.reset_connections()
        manager.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_find_user_ignores_case() -> None:
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=lambda: MagicMock(first=lambda: "user"))
    )
    assert await login_state.find_user(db, "Ada@Example.com") == "user"
    statement = str(db.execute.call_args.args[0])
    assert "lower" in statement


class TestProfile:
    def test_web_build_has_no_desktop_plugin(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(profile.DESKTOP_ENV, None)
            os.environ.pop(profile.DESKTOP_ROOT_ENV, None)
            assert rxconfig.desktop_plugins() == []
            assert rxconfig.cors_origins() is None

    def test_desktop_profile_is_added_last(self) -> None:
        env = {profile.DESKTOP_ENV: "1", "PROFILES": "local"}
        with patch.dict(os.environ, env):
            profile.activate_desktop_profile()
            assert os.environ["PROFILES"] == "local,desktop"
            profile.activate_desktop_profile()
            assert os.environ["PROFILES"] == "local,desktop"
            os.environ.pop(profile.DESKTOP_ROOT_ENV, None)
            assert rxconfig.cors_origins() is None

    def test_bundle_allows_only_the_webview(self) -> None:
        with patch.dict(os.environ, {profile.DESKTOP_ROOT_ENV: "/app"}):
            origins = rxconfig.cors_origins() or []
        assert origins == [*rxconfig.TAURI_ORIGINS, "http://127.0.0.1:18442"]

    def test_fake_profile_only_outside_the_bundle(self) -> None:
        env = {profile.DESKTOP_ENV: "1", "PROFILES": "", profile.FAKE_ENV: "a@b.c"}
        with patch.dict(os.environ, env):
            os.environ.pop(profile.DESKTOP_ROOT_ENV, None)
            profile.activate_desktop_profile()
            assert os.environ["PROFILES"] == "desktop,desktop_fake"
        with patch.dict(os.environ, {**env, profile.DESKTOP_ROOT_ENV: "/app"}):
            profile.activate_desktop_profile()
            assert os.environ["PROFILES"] == "desktop"

    def test_embedded_backend_runs_backend_only(self) -> None:
        with patch.dict(os.environ, {profile.DESKTOP_ROOT_ENV: "/app"}):
            os.environ.pop("REFLEX_BACKEND_ONLY", None)
            profile.prepare_embedded_backend()
            assert os.environ["REFLEX_BACKEND_ONLY"] == "true"

    def test_embedded_runtime_counts_as_desktop(self) -> None:
        with patch.dict(os.environ, {profile.DESKTOP_ROOT_ENV: "/app"}):
            assert profile.is_desktop()

    def test_desktop_profile_ships_no_secrets(self) -> None:
        script = _desktop_script()
        text = (ROOT / "configuration" / "config.desktop.yaml").read_text()
        resolved = script.resolve_build_time_values(text, lambda name: f"<{name}>")
        assert "secret:" not in resolved.split("#")[0]
        assert "oauth_providers: []" in text
        assert 'encryption_key: ""' in text
        assert f"backend_port: {rxconfig.DESKTOP_PORT}" in text


def _desktop_script() -> Any:
    spec = importlib.util.spec_from_file_location(
        "desktop_script", ROOT / "scripts" / "desktop.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestBuildScript:
    def test_payload_gets_yaml_profiles_only(self, tmp_path: Path) -> None:
        script = _desktop_script()
        root = tmp_path / "root"
        (root / "configuration").mkdir(parents=True)
        (root / "configuration" / "config.yaml").write_text("a: 1")
        (root / "configuration" / "config.prod.yaml").write_text("b: 2")
        (root / ".env").write_text("SECRET=1")
        copy = script.with_configuration(MagicMock(return_value="ok"))
        with patch.object(script.runtime, "_write_payload_stamp") as stamp:
            assert copy(root, tmp_path / "payload") == "ok"
        stamp.assert_called_once_with(tmp_path / "payload")
        payload = tmp_path / "payload"
        assert (payload / "configuration" / "config.yaml").exists()
        assert not (payload / "configuration" / "config.prod.yaml").exists()
        assert not (payload / ".env").exists()

    def test_public_ids_are_resolved_at_build_time(self, tmp_path: Path) -> None:
        script = _desktop_script()
        root = tmp_path / "root"
        (root / "configuration").mkdir(parents=True)
        (root / "configuration" / "config.desktop.yaml").write_text(
            "# a secret: in a comment is fine\n"
            "app:\n  desktop:\n    tenant_id: secret:tenant  # ID\n"
            "    client_id: secret:\n"
        )
        script.copy_configuration(
            root, tmp_path / "payload", lambda name: f"value-{name}"
        )
        text = (
            tmp_path / "payload" / "configuration" / "config.desktop.yaml"
        ).read_text()
        assert 'tenant_id: "value-tenant"' in text
        assert 'client_id: "value-client_id"' in text

    @pytest.mark.parametrize(
        "line",
        ["    password: secret:db-password", "    url: x secret:inline"],
    )
    def test_other_secrets_stop_the_build(self, line: str) -> None:
        script = _desktop_script()
        with pytest.raises(script.BuildError):
            script.resolve_build_time_values(line, lambda name: name)

    def test_stale_runtime_is_dropped(self, tmp_path: Path) -> None:
        script = _desktop_script()
        (tmp_path / "python" / "python" / "lib" / "python3.12").mkdir(parents=True)
        (tmp_path / "site-packages").mkdir()
        assert script.drop_stale_runtime(tmp_path, "3.14.6") is True
        assert not (tmp_path / "python").exists()
        assert script.drop_stale_runtime(tmp_path, "3.14.6") is False


class TestDevShellSync:
    def test_dev_shell_mirrors_production_and_is_idempotent(
        self, tmp_path: Path
    ) -> None:
        script = _desktop_script()
        dev = tmp_path / "tauri-dev" / "src-tauri"
        (dev / "src").mkdir(parents=True)
        (dev / "src" / "main.rs").write_text(
            '#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]\n'
            "fn main() {\n    // >>> reflex-desktop plugins >>>\n"
            "    // <<< reflex-desktop plugins <<<\n}\n"
        )
        (dev / "Cargo.toml").write_text('[package]\nversion = "0.1.0"\n\n[[bin]]\n')
        (dev / "tauri.conf.json").write_text('{"version": "0.1.0"}')
        (dev.parent / ".gitignore").write_text("/dist/\n")

        for _ in range(2):
            script.sync_dev_shell(script.SRC_TAURI, dev)

        main_rs = (dev / "src" / "main.rs").read_text()
        assert main_rs.count("mod app_menu;") == 1
        assert main_rs.count(".menu(build_menu)") == 1
        assert (dev / "src" / "app_menu.rs").exists()
        cargo = (dev / "Cargo.toml").read_text()
        assert cargo.count("objc2-app-kit") == 1
        prod = (script.SRC_TAURI / "Cargo.toml").read_text()
        assert re.search(r'^version = "([^"]*)"', cargo, re.M).group(1) == re.search(
            r'^version = "([^"]*)"', prod, re.M
        ).group(1)
        conf = json.loads((dev / "tauri.conf.json").read_text())
        assert conf["app"]["windows"][0]["windowEffects"]
        assert (dev.parent / ".gitignore").read_text().count("app_menu.rs") == 1
