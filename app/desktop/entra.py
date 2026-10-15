"""Microsoft Entra ID sign-in and per-user Postgres access for the desktop app.

The app is a public client: MSAL runs the authorization code flow with PKCE in
the system browser (loopback redirect), there is no client secret. The token
cache lives in the macOS Keychain, so the user stays signed in across starts.

Postgres sees every user with their own identity: each new connection gets a
fresh access token as password (`install_db_auth`). Connections opened before
sign-in fail with `NotSignedInError`, which the session checks treat as
"not logged in".
"""

import logging
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import msal
from platformdirs import user_data_dir
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.desktop.config import DesktopConfig

logger = logging.getLogger(__name__)

TOKEN_LIFETIME_FALLBACK: Final = 3600.0
"""Seconds an access token lives when Entra does not say (it usually does)."""
REFRESH_MARGIN: Final = 300.0
"""Renew this many seconds before the token expires."""
EXPIRY_SLACK: Final = 60.0
"""Never hand out a token that expires within this many seconds."""
RETRY_SECONDS: Final = 60.0
RESTORE_INTERVAL: Final = 30.0
"""Seconds between attempts to restore the cached account for a connection."""
KEYCHAIN_SERVICE: Final = "alloq"
KEYCHAIN_ACCOUNT: Final = "entra-token-cache"


class SignInError(Exception):
    """Sign-in failed; the message is shown to the user."""


class NotSignedInError(RuntimeError):
    """A database connection was attempted before the user signed in."""


@dataclass(frozen=True)
class Account:
    email: str
    name: str
    db_user: str


def token_cache(directory: Path | None = None) -> msal.TokenCache:
    """Encrypted token cache: Keychain on macOS, the OS store elsewhere."""
    from msal_extensions import (  # noqa: PLC0415  (optional native backends)
        PersistedTokenCache,
        build_encrypted_persistence,
    )
    from msal_extensions.persistence import KeychainPersistence  # noqa: PLC0415

    folder = directory or Path(user_data_dir("alloq", appauthor=False))
    folder.mkdir(parents=True, exist_ok=True)
    location = str(folder / "entra_token_cache")
    if sys.platform == "darwin":
        persistence = KeychainPersistence(location, KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
    else:
        persistence = build_encrypted_persistence(location)
    return PersistedTokenCache(persistence)


def _account(result: dict[str, Any], config: DesktopConfig) -> Account:
    if "access_token" not in result:
        detail = result.get("error_description") or result.get("error") or ""
        logger.warning("Entra sign-in failed: %s", result.get("error"))
        message = "Die Anmeldung bei Microsoft ist fehlgeschlagen."
        raise SignInError(f"{message} {detail}".strip())
    claims = result.get("id_token_claims") or {}
    email = str(claims.get("preferred_username") or claims.get("email") or "")
    if not email:
        raise SignInError("Das Microsoft-Konto liefert keine E-Mail-Adresse.")
    return Account(
        email=email,
        name=str(claims.get("name") or email),
        db_user=config.db_role or email,
    )


class EntraSignIn:
    """MSAL public client with the signed-in account of this app process.

    The access token is kept with its expiry and renewed by a background
    thread shortly before it runs out, so new database connections (opened on
    the event loop) rarely have to wait for Entra.
    """

    def __init__(
        self,
        config: DesktopConfig,
        cache: msal.TokenCache | None = None,
        client_factory: Callable[..., Any] = msal.PublicClientApplication,
        timer_factory: Callable[..., Any] = threading.Timer,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._cache = cache
        self._client_factory = client_factory
        self._timer_factory = timer_factory
        self._clock = clock
        self._client: Any = None
        self._account: Account | None = None
        self._token: str | None = None
        self._expires_at = 0.0
        self._timer: Any = None
        self._last_restore = float("-inf")
        self._lock = threading.Lock()

    @property
    def account(self) -> Account | None:
        return self._account

    def _app(self) -> Any:
        if not self._config.configured:
            raise SignInError(
                "Die Desktop-App ist nicht eingerichtet: Mandant und Client-ID "
                "fehlen in configuration/config.desktop.yaml."
            )
        if self._client is None:
            self._client = self._client_factory(
                self._config.client_id,
                authority=self._config.authority,
                token_cache=self._cache if self._cache is not None else token_cache(),
            )
        return self._client

    def _silent_result(self) -> dict[str, Any] | None:
        app = self._app()
        for cached in app.get_accounts():
            result = app.acquire_token_silent([self._config.db_scope], account=cached)
            if result and "access_token" in result:
                return result
        return None

    def _remember(self, result: dict[str, Any]) -> None:
        """Keep the token and schedule its renewal (caller holds the lock)."""
        lifetime = float(result.get("expires_in") or TOKEN_LIFETIME_FALLBACK)
        self._token = str(result["access_token"])
        self._expires_at = self._clock() + lifetime
        self._schedule_refresh(max(lifetime - REFRESH_MARGIN, RETRY_SECONDS))

    def _schedule_refresh(self, delay: float) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = self._timer_factory(delay, self._refresh_in_background)
        self._timer.daemon = True
        self._timer.start()

    def _refresh_in_background(self) -> None:
        """Renew the token off the event loop; retry soon on a failure."""
        with self._lock:
            if self._account is None:
                return
            try:
                result = self._silent_result()
            except Exception:
                logger.exception("Background token refresh failed")
                result = None
            if result is None:
                self._schedule_refresh(RETRY_SECONDS)
                return
            self._remember(result)

    def sign_in_silently(self) -> Account | None:
        """Use the cached account, without opening a browser."""
        with self._lock:
            result = self._silent_result()
            if result is None:
                return None
            self._account = _account(result, self._config)
            self._remember(result)
            return self._account

    def restore(self) -> Account | None:
        """The signed-in account, else the one cached in the Keychain.

        Lets a returning user keep working after an app restart without the
        sign-in page. Tries at most every `RESTORE_INTERVAL` seconds and never
        opens a browser.
        """
        if self._account is not None:
            return self._account
        now = self._clock()
        if now - self._last_restore < RESTORE_INTERVAL:
            return None
        self._last_restore = now
        try:
            return self.sign_in_silently()
        except SignInError:
            return None

    def sign_in_interactively(self) -> Account:
        """Browser sign-in with PKCE; blocks until done or timed out."""
        result = self._app().acquire_token_interactive(
            scopes=[self._config.db_scope],
            prompt="select_account",
            timeout=self._config.sign_in_timeout,
        )
        with self._lock:
            self._account = _account(result, self._config)
            self._remember(result)
            return self._account

    def access_token(self) -> str:
        """A valid Postgres access token.

        A failed refresh keeps the account: the connection attempt fails, the
        next one (or the background refresh) tries again.
        """
        with self._lock:
            if self._account is None:
                raise NotSignedInError("Not signed in")
            if self._token and self._clock() < self._expires_at - EXPIRY_SLACK:
                return self._token
            result = self._silent_result()
            if result is None:
                raise NotSignedInError("Token refresh failed")
            self._remember(result)
            return str(self._token)

    def sign_out(self) -> None:
        """Forget the account here and in the token cache."""
        with self._lock:
            self._account = None
            self._token = None
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            if self._client is not None:
                for cached in self._client.get_accounts():
                    self._client.remove_account(cached)


def connect_params(sign_in: EntraSignIn, cparams: dict[str, Any]) -> None:
    """Fill user and password of a new Postgres connection."""
    account = sign_in.restore()
    if account is None:
        raise NotSignedInError("Not signed in")
    cparams["user"] = account.db_user
    cparams["password"] = sign_in.access_token()


_installed: list[EntraSignIn] = []


def install_db_auth(sign_in: EntraSignIn) -> None:
    """Authenticate every new database connection with the user's token."""
    if _installed:
        _installed[0] = sign_in
        return
    _installed.append(sign_in)

    @event.listens_for(Engine, "do_connect")
    def _token_password(
        _dialect: Any, _record: Any, _cargs: Any, cparams: dict[str, Any]
    ) -> None:
        connect_params(_installed[0], cparams)
