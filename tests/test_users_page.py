"""Tests for the /admin/users page registration."""

from typing import Any

import reflex as rx
from reflex_base.registry import RegistrationContext

from appkit_user.user_management.states.user_states import UserState

from app.pages.users import create_users_page


def _on_load_handlers(route: str) -> list[Any]:
    for _, kwargs in RegistrationContext.ensure_context().decorated_pages:
        if kwargs.get("route") == route:
            return [getattr(h, "handler", h).fn for h in kwargs["on_load"]]
    msg = f"page {route} not registered"
    raise AssertionError(msg)


class TestUsersPage:
    def test_on_load_loads_users(self) -> None:
        create_users_page(rx.fragment(), route="/test/users")

        handlers = _on_load_handlers("/test/users")

        assert UserState.load_users.fn in handlers
