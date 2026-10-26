"""Tests for the splash-style login page."""

import json
from unittest.mock import patch

from reflex_base.registry import RegistrationContext

from appkit_user.authentication.states import LoginState

from app.pages.login import create_login_page, login_view


def _text(value: str) -> str:
    return json.dumps(value)[1:-1]


class TestLoginView:
    def test_uses_splash_background_and_app_icon(self) -> None:
        rendered = str(login_view())
        assert "--aq-splash-background" in rendered
        assert "alloq_icon.svg" in rendered
        assert "data-tauri-drag-region" in rendered

    def test_password_form_submits_to_login_state(self) -> None:
        rendered = str(login_view())
        assert "onSubmit:handleSubmit" in rendered
        assert 'name:"username"' in rendered
        assert 'name:"password"' in rendered
        assert _text("Passwort vergessen?") in rendered

    def test_single_sign_on_buttons(self) -> None:
        rendered = str(login_view())
        assert "Mit Microsoft anmelden" in rendered
        assert "Mit GitHub anmelden" in rendered
        assert "enable_azure_oauth" in rendered


def test_registers_route_and_clears_token_on_load() -> None:
    create_login_page(route="/test/login")
    for _, kwargs in RegistrationContext.ensure_context().decorated_pages:
        if kwargs.get("route") == "/test/login":
            handlers = [getattr(h, "handler", h).fn for h in kwargs["on_load"]]
            assert LoginState.clear_session_storage_token.fn in handlers
            return
    raise AssertionError("login page not registered")


def test_desktop_variant_signs_in_with_microsoft_only() -> None:
    with patch("app.pages.login.is_desktop", return_value=True):
        rendered = str(login_view())
    assert "sign_in_with_microsoft" in rendered
    assert "aq-splash" in rendered
    assert 'name:"password"' not in rendered
