"""Entra ID sign-in and per-user database credentials of the desktop app."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.desktop import entra
from app.desktop.config import POSTGRES_SCOPE, DesktopConfig
from app.desktop.entra import (
    Account,
    EntraSignIn,
    NotSignedInError,
    SignInError,
    connect_params,
)

CONFIG = DesktopConfig(tenant_id="tenant", client_id="client")
CLAIMS = {"preferred_username": "Ada@Example.com", "name": "Ada"}


def _token(value: str = "tok") -> dict[str, Any]:
    return {"access_token": value, "id_token_claims": CLAIMS}


class FakeClient:
    """Stand-in for msal.PublicClientApplication."""

    def __init__(self, client_id: str, **kwargs: Any) -> None:
        self.client_id = client_id
        self.kwargs = kwargs
        self.accounts: list[dict[str, str]] = []
        self.silent: dict[str, Any] | None = None
        self.interactive: dict[str, Any] = _token()
        self.removed: list[dict[str, str]] = []

    def get_accounts(self) -> list[dict[str, str]]:
        return self.accounts

    def acquire_token_silent(self, scopes: list[str], account: Any) -> Any:
        assert scopes == [POSTGRES_SCOPE]
        assert account in self.accounts
        return self.silent

    def acquire_token_interactive(self, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["scopes"] == [POSTGRES_SCOPE]
        assert kwargs["prompt"] == "select_account"
        return self.interactive

    def remove_account(self, account: dict[str, str]) -> None:
        self.removed.append(account)


def _sign_in(config: DesktopConfig = CONFIG) -> tuple[EntraSignIn, FakeClient]:
    clients: list[FakeClient] = []

    def factory(client_id: str, **kwargs: Any) -> FakeClient:
        clients.append(FakeClient(client_id, **kwargs))
        return clients[-1]

    sign_in = EntraSignIn(
        config,
        cache=MagicMock(),
        client_factory=factory,
        timer_factory=MagicMock(),
        clock=CLOCK,
    )
    sign_in._app()
    return sign_in, clients[0]


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


CLOCK = FakeClock()


class TestConfig:
    def test_placeholders_are_not_configured(self) -> None:
        assert not DesktopConfig().configured
        assert not DesktopConfig(tenant_id="<tenant-id>", client_id="x").configured
        assert CONFIG.configured
        assert CONFIG.authority == "https://login.microsoftonline.com/tenant"

    def test_unconfigured_app_refuses_sign_in(self) -> None:
        sign_in = EntraSignIn(DesktopConfig(), cache=MagicMock())
        with pytest.raises(SignInError, match="nicht eingerichtet"):
            sign_in.sign_in_silently()


class TestSignIn:
    def test_public_client_without_secret(self) -> None:
        _, client = _sign_in()
        assert client.client_id == "client"
        assert client.kwargs["authority"].endswith("/tenant")
        assert "client_credential" not in client.kwargs

    def test_silent_without_cached_account(self) -> None:
        sign_in, _ = _sign_in()
        assert sign_in.sign_in_silently() is None
        assert sign_in.account is None

    def test_silent_with_cached_account(self) -> None:
        sign_in, client = _sign_in()
        client.accounts = [{"username": "ada"}]
        client.silent = _token()
        account = sign_in.sign_in_silently()
        assert account == Account(
            email="Ada@Example.com", name="Ada", db_user="Ada@Example.com"
        )

    def test_interactive(self) -> None:
        sign_in, _ = _sign_in()
        assert sign_in.sign_in_interactively().email == "Ada@Example.com"
        assert sign_in.account is not None

    def test_group_role_is_the_database_user(self) -> None:
        sign_in, _ = _sign_in(CONFIG.model_copy(update={"db_role": "alloq-users"}))
        assert sign_in.sign_in_interactively().db_user == "alloq-users"

    def test_failed_sign_in_shows_the_reason(self) -> None:
        sign_in, client = _sign_in()
        client.interactive = {"error": "access_denied", "error_description": "Nö"}
        with pytest.raises(SignInError, match="Nö"):
            sign_in.sign_in_interactively()

    def test_account_without_email(self) -> None:
        sign_in, client = _sign_in()
        client.interactive = {"access_token": "t", "id_token_claims": {}}
        with pytest.raises(SignInError, match="E-Mail"):
            sign_in.sign_in_interactively()

    def test_sign_out_forgets_cached_accounts(self) -> None:
        sign_in, client = _sign_in()
        client.accounts = [{"username": "ada"}]
        sign_in.sign_in_interactively()
        sign_in.sign_out()
        assert sign_in.account is None
        assert client.removed == [{"username": "ada"}]


class TestAccessToken:
    def test_requires_sign_in(self) -> None:
        sign_in, _ = _sign_in()
        with pytest.raises(NotSignedInError):
            sign_in.access_token()

    def test_cached_token_until_shortly_before_expiry(self) -> None:
        sign_in, client = _sign_in()
        client.interactive = {**_token("first"), "expires_in": 3600}
        sign_in.sign_in_interactively()
        client.accounts = [{"username": "ada"}]
        client.silent = {**_token("fresh"), "expires_in": 3600}
        assert sign_in.access_token() == "first"
        CLOCK.now += 3600 - entra.EXPIRY_SLACK
        assert sign_in.access_token() == "fresh"

    def test_failed_refresh_keeps_the_account(self) -> None:
        sign_in, _ = _sign_in()
        sign_in.sign_in_interactively()
        CLOCK.now += 2 * entra.TOKEN_LIFETIME_FALLBACK
        with pytest.raises(NotSignedInError):
            sign_in.access_token()
        assert sign_in.account is not None


class TestBackgroundRefresh:
    def test_renewal_is_scheduled_before_expiry(self) -> None:
        sign_in, client = _sign_in()
        client.interactive = {**_token(), "expires_in": 3600}
        sign_in.sign_in_interactively()
        delay, callback = sign_in._timer_factory.call_args.args
        assert delay == 3600 - entra.REFRESH_MARGIN
        assert callback == sign_in._refresh_in_background

    def test_refresh_renews_the_token(self) -> None:
        sign_in, client = _sign_in()
        sign_in.sign_in_interactively()
        client.accounts = [{"username": "ada"}]
        client.silent = _token("renewed")
        sign_in._refresh_in_background()
        CLOCK.now += 1
        assert sign_in.access_token() == "renewed"

    def test_failed_refresh_retries_soon(self) -> None:
        sign_in, _ = _sign_in()
        sign_in.sign_in_interactively()
        sign_in._refresh_in_background()
        assert sign_in._timer_factory.call_args.args[0] == entra.RETRY_SECONDS

    def test_refresh_errors_are_retried(self) -> None:
        sign_in, client = _sign_in()
        sign_in.sign_in_interactively()
        client.accounts = [{"username": "ada"}]
        client.acquire_token_silent = MagicMock(side_effect=OSError("offline"))
        sign_in._refresh_in_background()
        assert sign_in._timer_factory.call_args.args[0] == entra.RETRY_SECONDS

    def test_no_refresh_after_sign_out(self) -> None:
        sign_in, _ = _sign_in()
        sign_in.sign_in_interactively()
        timer = sign_in._timer
        sign_in.sign_out()
        timer.cancel.assert_called()
        calls = sign_in._timer_factory.call_count
        sign_in._refresh_in_background()
        assert sign_in._timer_factory.call_count == calls


class TestConnectParams:
    def test_user_and_token_as_password(self) -> None:
        sign_in, client = _sign_in()
        sign_in.sign_in_interactively()
        client.accounts = [{"username": "ada"}]
        client.silent = _token("db-token")
        CLOCK.now += 2 * entra.TOKEN_LIFETIME_FALLBACK
        params: dict[str, Any] = {"user": "", "password": ""}
        connect_params(sign_in, params)
        assert params == {"user": "Ada@Example.com", "password": "db-token"}

    def test_no_connection_before_sign_in(self) -> None:
        sign_in, _ = _sign_in()
        with pytest.raises(NotSignedInError):
            connect_params(sign_in, {})

    def test_cached_account_is_restored_for_a_connection(self) -> None:
        sign_in, client = _sign_in()
        client.accounts = [{"username": "ada"}]
        client.silent = _token("from-keychain")
        params: dict[str, Any] = {}
        connect_params(sign_in, params)
        assert params == {"user": "Ada@Example.com", "password": "from-keychain"}

    def test_restore_is_throttled(self) -> None:
        sign_in, client = _sign_in()
        client.acquire_token_silent = MagicMock(return_value=None)
        client.accounts = [{"username": "ada"}]
        assert sign_in.restore() is None
        assert sign_in.restore() is None
        assert client.acquire_token_silent.call_count == 1
        CLOCK.now += entra.RESTORE_INTERVAL
        sign_in.restore()
        assert client.acquire_token_silent.call_count == 2

    def test_restore_without_configuration(self) -> None:
        sign_in = EntraSignIn(DesktopConfig(), cache=MagicMock(), clock=CLOCK)
        assert sign_in.restore() is None

    def test_install_registers_once_and_swaps_provider(self) -> None:
        first, _ = _sign_in()
        second, _ = _sign_in()
        with (
            patch.object(entra, "_installed", []),
            patch.object(entra.event, "listens_for") as listens_for,
        ):
            listens_for.return_value = lambda fn: fn
            entra.install_db_auth(first)
            entra.install_db_auth(second)
            assert listens_for.call_count == 1
            assert entra._installed == [second]


def test_token_cache_uses_keychain_on_macos(tmp_path: Any) -> None:
    with (
        patch.object(entra.sys, "platform", "darwin"),
        patch("msal_extensions.persistence.KeychainPersistence") as keychain,
        patch("msal_extensions.PersistedTokenCache") as cache,
    ):
        entra.token_cache(tmp_path)
    keychain.assert_called_once_with(
        str(tmp_path / "entra_token_cache"),
        entra.KEYCHAIN_SERVICE,
        entra.KEYCHAIN_ACCOUNT,
    )
    cache.assert_called_once()
