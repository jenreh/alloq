"""Tests for app.app module."""

from unittest.mock import MagicMock

import reflex as rx

from appkit_commons.middleware import ForceHTTPSMiddleware

from app.app import add_https_middleware, index


class TestAddHttpsMiddleware:
    def test_wraps_with_force_https_middleware(self) -> None:

        mock_asgi_app = MagicMock()
        result = add_https_middleware(mock_asgi_app)

        assert isinstance(result, ForceHTTPSMiddleware)

    def test_returns_non_none(self) -> None:

        result = add_https_middleware(MagicMock())

        assert result is not None


class TestIndexPage:
    def test_index_returns_component(self) -> None:
        result = index()

        assert isinstance(result, rx.Component)
