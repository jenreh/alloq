"""Tests for app.configuration module."""

from unittest.mock import MagicMock, patch

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
        mock_registry.configure.assert_called_once_with(AppConfig, env_file="/.env")

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
        assert kwargs.get("env_file") == "/.env"
