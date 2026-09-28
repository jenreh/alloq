"""Tests for app.app module."""

from unittest.mock import MagicMock, patch

from appkit_commons.middleware import ForceHTTPSMiddleware
from appkit_user.authentication import add_session_guard
from appkit_user.authentication.session_filter import SessionFilter

from app import app as app_module
from app.app import add_https_middleware
from app.configuration import AppConfig


def _config_with_proxies(proxies: set[str] | None) -> MagicMock:
    config = MagicMock()
    config.app.trusted_proxies = proxies
    return config


class TestAddHttpsMiddleware:
    def test_wraps_with_force_https_middleware(self) -> None:

        mock_asgi_app = MagicMock()
        result = add_https_middleware(mock_asgi_app)

        assert isinstance(result, ForceHTTPSMiddleware)

    def test_returns_non_none(self) -> None:

        result = add_https_middleware(MagicMock())

        assert result is not None

    def test_passes_configured_trusted_proxies(self) -> None:
        proxies = {"10.0.0.1", "10.0.0.2"}

        with patch("app.app.configure", return_value=_config_with_proxies(proxies)):
            result = add_https_middleware(MagicMock())

        assert isinstance(result, ForceHTTPSMiddleware)
        assert result.trusted_hosts == proxies

    async def test_ignores_forwarded_proto_from_untrusted_peer(self) -> None:
        seen: dict[str, str] = {}

        async def _inner(scope: dict, _receive: object, _send: object) -> None:
            seen["scheme"] = scope["scheme"]

        with patch(
            "app.app.configure", return_value=_config_with_proxies({"10.0.0.1"})
        ):
            middleware = add_https_middleware(_inner)

        scope = {
            "type": "http",
            "scheme": "http",
            "client": ("203.0.113.9", 1234),
            "headers": [(b"x-forwarded-proto", b"https")],
        }
        await middleware(scope, MagicMock(), MagicMock())

        assert seen["scheme"] == "http"


class TestAppConfigTrustedProxies:
    def test_defaults_to_none(self) -> None:
        assert AppConfig.model_fields["trusted_proxies"].default is None


class TestAppWiring:
    def test_session_guard_installed(self) -> None:
        assert add_session_guard in app_module.app.api_transformer

    def test_https_middleware_installed(self) -> None:
        assert add_https_middleware in app_module.app.api_transformer

    def test_session_filter_installed(self) -> None:
        middlewares = app_module.app._middlewares

        assert any(isinstance(m, SessionFilter) for m in middlewares)
