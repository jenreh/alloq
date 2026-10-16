"""Tests for the /admin/users page registration."""

from typing import Any, cast
from unittest.mock import patch

import reflex as rx
from reflex_base.registry import RegistrationContext

from appkit_user.user_management.components.user import user_table_view
from appkit_user.user_management.states.user_states import UserState

from app.components.db_access_button import database_access_button
from app.desktop.db_access_state import DatabaseAccessState
from app.pages import users
from app.pages.users import create_users_page, row_actions


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

        assert cast("Any", UserState.load_users).fn in handlers

    def test_on_load_loads_database_access(self) -> None:
        create_users_page(rx.fragment(), route="/test/users-db")

        handlers = _on_load_handlers("/test/users-db")

        assert cast("Any", DatabaseAccessState.load).fn in handlers

    def test_database_access_button_only_in_the_desktop_app(self) -> None:
        with patch.object(users, "is_desktop", return_value=True):
            assert row_actions() == [database_access_button]
        with patch.object(users, "is_desktop", return_value=False):
            assert row_actions() == []

    def test_database_access_button_renders_in_the_user_table(self) -> None:
        rendered = str(
            user_table_view(additional_components=[database_access_button]).render()
        )

        assert "Datenbankzugriff" in rendered
