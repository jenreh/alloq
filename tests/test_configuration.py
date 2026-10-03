"""Tests for app.configuration module."""

from unittest.mock import MagicMock, patch

import pytest

from app.configuration import AppConfig, configure


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


# ── base_path: serving below a URL prefix ───────────────────────────────────


def _app_config(base_path: str, providers: list[dict]) -> AppConfig:
    return AppConfig.model_validate(
        {
            "version": "0",
            "name": "test",
            "logging": "logging.yaml",
            "base_path": base_path,
            "authentication": {
                "server_url": "https://apps.example.com",
                "server_port": 443,
                "oauth_providers": providers,
            },
        }
    )


_GITHUB = {"provider": "github", "client_id": "id", "client_secret": "secret"}


class TestBasePath:
    def test_defaults_to_site_root(self) -> None:
        assert _app_config("", []).base_path == ""

    @pytest.mark.parametrize("raw", ["/alloq", "alloq", "/alloq/", " alloq/ "])
    def test_normalizes_to_leading_slash_without_trailing_slash(self, raw: str) -> None:
        assert _app_config(raw, []).base_path == "/alloq"

    @pytest.mark.parametrize("raw", ["/", "  "])
    def test_bare_slash_means_site_root(self, raw: str) -> None:
        assert _app_config(raw, []).base_path == ""

    def test_oauth_redirect_includes_base_path(self) -> None:
        app_config = _app_config("/alloq", [_GITHUB])

        provider = app_config.authentication.oauth_providers[0]
        assert provider.redirect_url == (
            "https://apps.example.com:443/alloq/oauth/github/callback"
        )

    def test_explicit_redirect_url_is_kept(self) -> None:
        explicit = {**_GITHUB, "redirect_url": "https://sso.example.com/cb"}

        app_config = _app_config("/alloq", [explicit])

        provider = app_config.authentication.oauth_providers[0]
        assert provider.redirect_url == "https://sso.example.com/cb"

    def test_site_root_leaves_redirect_to_appkit_default(self) -> None:
        app_config = _app_config("", [_GITHUB])

        assert app_config.authentication.oauth_providers[0].redirect_url is None
