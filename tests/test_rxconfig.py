"""Tests for the Reflex configuration built in rxconfig.py."""

from unittest.mock import MagicMock, patch

import pytest

import rxconfig
from appkit_commons.configuration.configuration import ReflexConfig


class TestUrlSettings:
    def test_passes_configured_urls(self) -> None:
        reflex = ReflexConfig(
            deploy_url="https://alloq.example.com",
            api_url="https://api.alloq.example.com",
        )

        assert rxconfig._url_settings(reflex) == {
            "deploy_url": "https://alloq.example.com",
            "api_url": "https://api.alloq.example.com",
        }

    def test_omits_unset_urls(self) -> None:
        reflex = ReflexConfig(deploy_url="https://alloq.example.com")

        assert rxconfig._url_settings(reflex) == {
            "deploy_url": "https://alloq.example.com"
        }

    def test_no_reflex_block(self) -> None:
        assert rxconfig._url_settings(None) == {}


class TestRequireDatabase:
    def test_missing_database_fails_with_clear_error(self) -> None:
        registry = MagicMock()
        registry.get.side_effect = KeyError("DatabaseConfig")

        with (
            patch("rxconfig.service_registry", return_value=registry),
            pytest.raises(RuntimeError, match=r"app\.database"),
        ):
            rxconfig._require_database()

    def test_returns_registered_database(self) -> None:
        database = MagicMock()
        registry = MagicMock()
        registry.get.return_value = database

        with patch("rxconfig.service_registry", return_value=registry):
            assert rxconfig._require_database() is database
