"""Public URL of the app when a reverse proxy serves it under a path prefix.

The hosting platform sets ``PUBLIC_BASE_URL`` (origin, e.g.
``https://apps.example.com``) and ``PUBLIC_PATH_PREFIX`` (e.g. ``/alloq``).
All absolute URLs the backend hands out (OAuth callbacks, password reset
links, image API links) are derived from them, so no deployment URL is
hard-coded in the configuration.
"""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Self
from urllib.parse import urlsplit

from appkit_commons.configuration.configuration import ReflexConfig
from appkit_user.configuration import AuthenticationConfiguration

logger = logging.getLogger(__name__)

PUBLIC_BASE_URL_ENV: Final[str] = "PUBLIC_BASE_URL"
PUBLIC_PATH_PREFIX_ENV: Final[str] = "PUBLIC_PATH_PREFIX"
OAUTH_CALLBACK_PATH: Final[str] = "/oauth/{provider}/callback"
DEFAULT_API_URL: Final[str] = "http://localhost:3030"
DEFAULT_DEPLOY_URL: Final[str] = "http://localhost:8080"

_ALLOWED_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})
_FORBIDDEN_PREFIX_CHARS: Final[frozenset[str]] = frozenset("?#\\ ")


class PublicUrlError(ValueError):
    """Raised when the public URL settings are malformed."""


def _normalize_base_url(base_url: str) -> str:
    parts = urlsplit(base_url.strip())
    if parts.scheme not in _ALLOWED_SCHEMES or not parts.netloc:
        msg = f"{PUBLIC_BASE_URL_ENV} must be an http(s) origin, got {base_url!r}"
        raise PublicUrlError(msg)
    if parts.path.strip("/") or parts.query or parts.fragment:
        msg = (
            f"{PUBLIC_BASE_URL_ENV} must not contain a path, query or fragment; "
            f"put the path into {PUBLIC_PATH_PREFIX_ENV} (got {base_url!r})"
        )
        raise PublicUrlError(msg)
    return f"{parts.scheme}://{parts.netloc}"


def _normalize_path_prefix(path_prefix: str) -> str:
    stripped = path_prefix.strip().strip("/")
    if not stripped:
        return ""
    if "//" in stripped or _FORBIDDEN_PREFIX_CHARS.intersection(stripped):
        msg = f"{PUBLIC_PATH_PREFIX_ENV} must be a plain path, got {path_prefix!r}"
        raise PublicUrlError(msg)
    return f"/{stripped}"


@dataclass(frozen=True, slots=True)
class PublicUrl:
    """Origin and path prefix under which browsers reach this app."""

    base_url: str
    path_prefix: str = ""

    @classmethod
    def create(cls, base_url: str, path_prefix: str = "") -> Self:
        """Build a normalized public URL; raises PublicUrlError if malformed."""
        return cls(
            base_url=_normalize_base_url(base_url),
            path_prefix=_normalize_path_prefix(path_prefix),
        )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Self | None:
        """Read the public URL from the environment; None when not configured."""
        env = os.environ if environ is None else environ
        base_url = env.get(PUBLIC_BASE_URL_ENV, "").strip()
        path_prefix = env.get(PUBLIC_PATH_PREFIX_ENV, "")
        if not base_url:
            if path_prefix.strip("/ "):
                logger.warning(
                    "%s is ignored because %s is not set",
                    PUBLIC_PATH_PREFIX_ENV,
                    PUBLIC_BASE_URL_ENV,
                )
            return None
        return cls.create(base_url, path_prefix)

    @property
    def default_port(self) -> int:
        """Default port of the scheme; an explicit port is part of base_url."""
        return 443 if self.base_url.startswith("https:") else 80

    @property
    def app_url(self) -> str:
        """Absolute URL of the app root, without a trailing slash."""
        return f"{self.base_url}{self.path_prefix}"

    def url(self, path: str) -> str:
        """Absolute public URL for an app-relative path such as ``/login``."""
        return f"{self.app_url}/{path.lstrip('/')}"


def apply_public_url(
    public_url: PublicUrl,
    reflex: ReflexConfig | None,
    authentication: AuthenticationConfiguration,
) -> None:
    """Derive every public URL in the loaded configuration from ``public_url``.

    The appkit ReflexConfig URLs are what appkit components use to build links
    to the backend API (e.g. ``/api/images``) and the MCP OAuth callback, so
    they include the prefix. Any explicit port is already part of ``base_url``:
    ``frontend_port`` is set to the scheme default and ``server_port`` to 0 so
    appkit does not append a port after the path.
    """
    if reflex is not None:
        reflex.deploy_url = public_url.app_url
        reflex.api_url = public_url.app_url
        reflex.frontend_port = public_url.default_port
    authentication.server_url = public_url.app_url
    authentication.server_port = 0
    for oauth in authentication.oauth_providers:
        oauth.redirect_url = public_url.url(
            OAUTH_CALLBACK_PATH.format(provider=oauth.provider.value)
        )
    logger.info("Public app URL: %s", public_url.app_url)


def reflex_server_urls(
    public_url: PublicUrl | None, reflex: ReflexConfig | None
) -> tuple[str, str]:
    """Return ``(api_url, deploy_url)`` for ``rx.Config``.

    Reflex adds ``backend_path`` / ``frontend_path`` itself, so behind a proxy
    both URLs are the bare origin. Without a public URL the configured values
    (local development) are used unchanged.
    """
    if public_url is not None:
        return public_url.base_url, public_url.base_url
    if reflex is None:
        return DEFAULT_API_URL, DEFAULT_DEPLOY_URL
    return (
        reflex.api_url or DEFAULT_API_URL,
        reflex.deploy_url or DEFAULT_DEPLOY_URL,
    )
