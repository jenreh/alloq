"""Tests for app.configuration module."""

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from appkit_commons.configuration.configuration import Environment

from app.configuration import AppConfig, check_production_security, configure


def _app(environment: Environment, *, secure: bool, proxies: set[str] | None) -> Any:
    return SimpleNamespace(
        environment=environment,
        trusted_proxies=proxies,
        authentication=SimpleNamespace(session_cookie_secure=secure),
    )


class TestCheckProductionSecurity:
    def test_production_rejects_insecure_cookie(self) -> None:
        app = _app(Environment.production, secure=False, proxies={"10.0.0.4"})

        with pytest.raises(RuntimeError, match="session_cookie_secure"):
            check_production_security(app)

    def test_production_warns_without_trusted_proxies(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        app = _app(Environment.production, secure=True, proxies=None)

        with caplog.at_level(logging.WARNING, logger="app.configuration"):
            check_production_security(app)

        assert "trusted_proxies" in caplog.text

    def test_production_with_proxies_is_quiet(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        app = _app(Environment.production, secure=True, proxies={"10.0.0.4"})

        with caplog.at_level(logging.WARNING, logger="app.configuration"):
            check_production_security(app)

        assert caplog.text == ""

    def test_other_environments_may_use_plain_cookies(self) -> None:
        app = _app(Environment.local, secure=False, proxies=None)

        check_production_security(app)


def _validate_proxies(value: Any) -> set[str] | None:
    """Validate without the YAML sources, as a nested config section would."""
    return AppConfig.model_validate(
        {
            "version": "1",
            "name": "Alloq",
            "logging": "logging.yaml",
            "authentication": {"server_url": "http://localhost", "server_port": 0},
            "trusted_proxies": value,
        }
    ).trusted_proxies


class TestTrustedProxies:
    def test_secret_holds_comma_separated_addresses(self) -> None:
        with patch(
            "appkit_commons.configuration.base.get_secret",
            return_value="127.0.0.1, ::1",
        ) as get_secret:
            proxies = _validate_proxies("secret:common-allowed-proxies")

        get_secret.assert_called_once_with("common-allowed-proxies")
        assert proxies == {"127.0.0.1", "::1"}

    def test_empty_value_trusts_no_peer(self) -> None:
        assert _validate_proxies(" , ") == set()

    def test_list_stays_supported(self) -> None:
        assert _validate_proxies(["10.0.0.4"]) == {"10.0.0.4"}

    def test_none_trusts_every_peer(self) -> None:
        assert _validate_proxies(None) is None


class TestAppConfig:
    def test_has_authentication_field(self) -> None:
        assert "authentication" in AppConfig.model_fields

    def test_inherits_base_fields(self) -> None:
        for field in ("version", "name", "environment"):
            assert field in AppConfig.model_fields


class TestConfigure:
    def setup_method(self) -> None:
        configure.cache_clear()

    def test_configure_calls_service_registry(self) -> None:
        mock_result = MagicMock()
        mock_registry = MagicMock()
        mock_registry.configure.return_value = mock_result

        with patch("app.configuration.service_registry", return_value=mock_registry):
            result = configure()

        assert result is mock_result
        mock_registry.configure.assert_called_once_with(AppConfig, env_file=".env")

    def test_configure_is_cached(self) -> None:
        mock_registry = MagicMock()
        mock_registry.configure.return_value = MagicMock()

        with patch("app.configuration.service_registry", return_value=mock_registry):
            result1 = configure()
            result2 = configure()

        assert result1 is result2
        mock_registry.configure.assert_called_once()

    def test_configure_passes_env_file(self) -> None:
        mock_registry = MagicMock()
        with patch("app.configuration.service_registry", return_value=mock_registry):
            configure()

        _args, kwargs = mock_registry.configure.call_args
        assert kwargs.get("env_file") == ".env"
