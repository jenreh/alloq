"""Tests for the employee read access and the project manager edit access."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import reflex as rx
from alloq_commons.access import (
    CAN_EDIT,
    CAN_VIEW,
    IS_ADMIN,
    NO_ACCESS_MSG,
    admin_only,
    can_edit,
    can_edit_offers,
    can_view,
    editor_only,
    no_access,
    requires_editor,
    requires_offer_editor,
    requires_viewer,
    viewer_only,
)
from alloq_commons.roles import (
    ALL_ROLES,
    EMPLOYEE_ROLE,
    OFFER_EDITOR_ROLE,
    PROJECT_MANAGER_ROLE,
)

from appkit_user.authentication.backend.models import User

ADMIN = User(user_id=1, is_admin=True)
EMPLOYEE = User(user_id=2, roles=[EMPLOYEE_ROLE.name])
MANAGER = User(user_id=3, roles=[PROJECT_MANAGER_ROLE.name])
OTHER = User(user_id=4, roles=["department_1"])
OFFER_EDITOR = User(user_id=5, roles=[OFFER_EDITOR_ROLE.name])
NO_ROLES = User(user_id=6)


class _FakeLogin:
    def __init__(self, user: User | None) -> None:
        self._user = user
        self.redirected = False

    @property
    async def authenticated_user(self) -> User | None:
        return self._user

    async def redir(self) -> str:
        self.redirected = True
        return "redirect"


class _Reader:
    def __init__(self, user: User | None) -> None:
        self.login = _FakeLogin(user)
        self.get_state = AsyncMock(return_value=self.login)
        self.calls = 0

    @requires_viewer
    async def read(self, value: int) -> int:
        self.calls += 1
        return value * 2

    @requires_viewer
    async def stream(self) -> AsyncGenerator[Any]:
        self.calls += 1
        yield "loaded"


class _Editor(_Reader):
    @requires_editor
    async def save(self, value: int) -> int:
        self.calls += 1
        return value + 1

    @requires_editor
    async def save_stream(self) -> AsyncGenerator[Any]:
        self.calls += 1
        yield "saved"


async def _collect(gen: AsyncGenerator[Any]) -> list[Any]:
    return [item async for item in gen]


class TestEmployeeRole:
    def test_employee_role_is_offered_in_user_management(self) -> None:
        assert EMPLOYEE_ROLE in ALL_ROLES
        assert EMPLOYEE_ROLE.name == "employee"
        assert len({role.name for role in ALL_ROLES}) == len(ALL_ROLES)


class TestCanView:
    @pytest.mark.parametrize(
        ("user", "expected"),
        [(ADMIN, True), (MANAGER, True), (EMPLOYEE, True), (OTHER, False)],
    )
    def test_admins_managers_and_employees_may_read(
        self, user: User, expected: bool
    ) -> None:
        assert can_view(user) is expected


class TestCanEdit:
    @pytest.mark.parametrize(
        ("user", "expected"),
        [(ADMIN, True), (MANAGER, True), (EMPLOYEE, False), (OTHER, False)],
    )
    def test_admins_and_project_managers_may_edit(
        self, user: User, expected: bool
    ) -> None:
        assert can_edit(user) is expected


class TestRequiresEditor:
    @pytest.mark.parametrize("user", [ADMIN, MANAGER])
    async def test_admins_and_project_managers_run_the_handler(
        self, user: User
    ) -> None:
        editor = _Editor(user)
        assert await editor.save(3) == 4
        assert await _collect(editor.save_stream()) == ["saved"]
        assert editor.calls == 2

    @pytest.mark.parametrize("user", [EMPLOYEE, OTHER])
    async def test_readers_and_others_are_denied(self, user: User) -> None:
        editor = _Editor(user)
        assert await editor.save(3) is not None
        assert len(await _collect(editor.save_stream())) == 1
        assert editor.calls == 0

    async def test_anonymous_users_are_redirected(self) -> None:
        editor = _Editor(None)
        assert await editor.save(3) == "redirect"
        assert editor.login.redirected
        assert editor.calls == 0

    def test_keeps_the_handler_name(self) -> None:
        assert _Editor.save.__name__ == "save"


class TestRequiresViewer:
    @pytest.mark.parametrize("user", [ADMIN, MANAGER, EMPLOYEE])
    async def test_allowed_users_run_the_handler(self, user: User) -> None:
        reader = _Reader(user)
        assert await reader.read(3) == 6
        assert await _collect(reader.stream()) == ["loaded"]
        assert reader.calls == 2

    async def test_other_users_get_an_error_and_the_handler_does_not_run(
        self,
    ) -> None:
        reader = _Reader(OTHER)
        result = await reader.read(3)
        events = await _collect(reader.stream())
        assert reader.calls == 0
        assert result is not None
        assert len(events) == 1
        assert events[0] is not None

    async def test_anonymous_users_are_redirected(self) -> None:
        reader = _Reader(None)
        assert await reader.read(3) == "redirect"
        assert await _collect(reader.stream()) == ["redirect"]
        assert reader.login.redirected
        assert reader.calls == 0

    async def test_denial_is_not_mistaken_for_access_when_redirect_is_none(
        self,
    ) -> None:
        reader = _Reader(None)
        reader.login.redir = AsyncMock(return_value=None)  # ty: ignore[invalid-assignment]
        assert await reader.read(3) is None
        assert reader.calls == 0

    def test_keeps_the_handler_name(self) -> None:
        assert _Reader.read.__name__ == "read"


class TestRenderGuards:
    def test_viewer_only_checks_admin_or_employee_role(self) -> None:
        rendered = str(viewer_only(rx.text("x")))
        assert "is_admin" in rendered
        assert EMPLOYEE_ROLE.name in rendered

    def test_admin_only_checks_admin_flag(self) -> None:
        rendered = str(admin_only(rx.text("x")))
        assert "is_admin" in rendered
        assert EMPLOYEE_ROLE.name not in rendered
        assert PROJECT_MANAGER_ROLE.name not in rendered

    def test_editor_only_checks_admin_or_project_manager_role(self) -> None:
        rendered = str(editor_only(rx.text("x")))
        assert "is_admin" in rendered
        assert PROJECT_MANAGER_ROLE.name in rendered
        assert EMPLOYEE_ROLE.name not in rendered

    def test_viewer_only_includes_project_managers(self) -> None:
        assert PROJECT_MANAGER_ROLE.name in str(CAN_VIEW)
        assert PROJECT_MANAGER_ROLE.name in str(CAN_EDIT)

    def test_can_view_includes_admin_flag_and_role(self) -> None:
        assert "is_admin" in str(CAN_VIEW)
        assert EMPLOYEE_ROLE.name in str(CAN_VIEW)
        assert "is_admin" in str(IS_ADMIN)

    def test_no_access_explains_the_missing_rights(self) -> None:
        # Reflex escapes umlauts on render; the message has none up to here.
        assert NO_ACCESS_MSG.split(",")[0] in str(no_access())

    def test_fallback_is_rendered(self) -> None:
        rendered = str(viewer_only(rx.text("inside"), fallback=rx.text("outside")))
        assert "inside" in rendered
        assert "outside" in rendered


class _OfferEditor(_Reader):
    @requires_offer_editor
    async def save(self, value: int) -> int:
        self.calls += 1
        return value + 1


class TestOfferEditor:
    def test_role_is_offered_in_user_management(self) -> None:
        assert OFFER_EDITOR_ROLE in ALL_ROLES
        assert OFFER_EDITOR_ROLE.name == "offer_editor"
        assert OFFER_EDITOR_ROLE.label == "Angebote"

    @pytest.mark.parametrize(
        ("user", "expected"),
        [
            (ADMIN, False),
            (MANAGER, False),
            (OFFER_EDITOR, True),
            (EMPLOYEE, False),
            (OTHER, False),
            (NO_ROLES, False),
        ],
    )
    def test_can_edit_offers(self, user: User, expected: bool) -> None:
        assert can_edit_offers(user) is expected

    def test_offer_editor_gets_no_planning_access(self) -> None:
        assert can_edit(OFFER_EDITOR) is False
        assert can_view(OFFER_EDITOR) is False

    async def test_offer_editors_run_the_handler(self) -> None:
        editor = _OfferEditor(OFFER_EDITOR)
        assert await editor.save(1) == 2

    @pytest.mark.parametrize("user", [ADMIN, MANAGER, EMPLOYEE, OTHER, NO_ROLES])
    async def test_others_are_denied(self, user: User) -> None:
        editor = _OfferEditor(user)
        assert await editor.save(1) is not None
        assert editor.calls == 0

    async def test_anonymous_users_are_redirected(self) -> None:
        editor = _OfferEditor(None)
        assert await editor.save(1) == "redirect"
        assert editor.calls == 0


def test_no_access_links_to_the_offers_for_everyone() -> None:
    rendered = str(no_access())
    assert '"/offers"' in rendered
    assert "user.roles" not in rendered
