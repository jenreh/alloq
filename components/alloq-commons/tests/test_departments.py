"""Tests for department management and department permission roles."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_commons.components.department import (
    department_form_fields,
    departments_table,
    departments_toolbar,
)
from alloq_commons.entities import DepartmentEntity, EmployeeEntity
from alloq_commons.models import Department, DepartmentCreate
from alloq_commons.roles import (
    ALL_ROLES,
    DEPARTMENT_ROLE_GROUP,
    department_role_name,
    department_roles,
)
from alloq_commons.state.department_states import DepartmentState
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from appkit_user.authentication.states import LoginState
from appkit_user.user_management.states.user_states import UserState

MODULE = "alloq_commons.state.department_states"


def _entity(dept_id: int = 3, name: str = "Informationstechnik") -> DepartmentEntity:
    entity = DepartmentEntity(name=name, abbreviation="IT")
    entity.id = dept_id
    return entity


@pytest.fixture
def repo() -> Iterator[AsyncMock]:
    """Patch the department repository and the DB session."""
    session = AsyncMock()

    @asynccontextmanager
    async def _ctx() -> AsyncIterator[Any]:
        yield session

    mock = AsyncMock()
    mock.find_all_paginated = AsyncMock(return_value=[_entity()])
    with (
        patch(f"{MODULE}.department_repo", mock),
        patch(f"{MODULE}.get_asyncdb_session", _ctx),
    ):
        yield mock


@contextmanager
def _as_admin(state: DepartmentState, **others: Any) -> Iterator[None]:
    user = MagicMock(is_admin=True, user_id=1)

    async def _user() -> MagicMock:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value=None)

    async def _get_state(cls: type) -> Any:
        return login if cls is LoginState else others[cls.__name__]

    object.__setattr__(state, "get_state", _get_state)
    try:
        yield
    finally:
        object.__delattr__(state, "get_state")


async def _run(handler: Any, *args: Any) -> str:
    """Drive a handler and return its toasts as text."""
    result = handler(*args)
    if hasattr(result, "__aiter__"):
        return " ".join([str(i) async for i in result if i is not None])
    await result
    return ""


class TestDepartmentModels:
    def test_to_dict(self) -> None:
        assert _entity().to_dict()["abbreviation"] == "IT"

    def test_department_highlight_defaults_to_false(self) -> None:
        assert Department(id=3).highlighted is False

    def test_label_shows_name_and_abbreviation(self) -> None:
        department = Department(id=3, name="Informationstechnik", abbreviation="IT")
        assert department.label == "Informationstechnik (IT)"

    def test_department_form_includes_highlight_toggle(self) -> None:
        rendered = str(department_form_fields())
        assert "highlighted" in rendered

    @pytest.mark.parametrize(
        "data",
        [
            {"name": "", "abbreviation": "IT"},
            {"name": "IT", "abbreviation": ""},
            {"name": "IT", "abbreviation": "X" * 11},
        ],
    )
    def test_create_requires_name_and_short_abbreviation(
        self, data: dict[str, str]
    ) -> None:
        with pytest.raises(ValidationError):
            DepartmentCreate(**data)

    def test_employee_to_dict_includes_department(self) -> None:
        employee = EmployeeEntity(first_name="A", last_name="B", seniority="Senior")
        employee.id = 1
        employee.roles = []
        employee.absences = []
        employee.department_id = 3
        employee.department = _entity()
        data = employee.to_dict()
        assert data["department_id"] == 3
        assert data["department"]["abbreviation"] == "IT"

    def test_employee_without_department(self) -> None:
        employee = EmployeeEntity(first_name="A", last_name="B", seniority="Senior")
        employee.id = 1
        employee.roles = []
        employee.absences = []
        assert employee.to_dict()["department"] is None


class TestDepartmentRoles:
    def test_role_name_uses_id(self) -> None:
        assert department_role_name(3) == "department_3"

    def test_one_role_per_department_in_own_group(self) -> None:
        roles = department_roles(
            [Department(id=3, name="Informationstechnik", abbreviation="IT")]
        )
        assert [(r.name, r.label, r.group) for r in roles] == [
            ("department_3", "Informationstechnik (IT)", DEPARTMENT_ROLE_GROUP)
        ]

    @pytest.mark.usefixtures("repo")
    async def test_user_management_offers_app_and_department_roles(self) -> None:
        state = DepartmentState()
        users = UserState()
        with _as_admin(state, UserState=users):
            await _run(state.load_user_roles)

        names = [r["name"] for r in users.available_roles]
        assert names == [*(r.name for r in ALL_ROLES), "department_3"]
        assert users.sorted_group_names[-1] == DEPARTMENT_ROLE_GROUP


class TestDepartmentState:
    @pytest.mark.usefixtures("repo")
    async def test_load(self) -> None:
        state = DepartmentState()
        with _as_admin(state):
            await _run(state.load_departments)
        assert [d.abbreviation for d in state.departments] == ["IT"]
        assert state.is_loading is False

    def test_filter_matches_name_or_abbreviation(self) -> None:
        state = DepartmentState()
        state.departments = [
            Department(id=1, name="Informationstechnik", abbreviation="IT"),
            Department(id=2, name="Personal", abbreviation="HR"),
        ]
        state.search_filter = "hr"
        assert [d.id for d in state.filtered_departments] == [2]
        state.search_filter = "informa"
        assert [d.id for d in state.filtered_departments] == [1]

    async def test_create(self, repo: AsyncMock) -> None:
        state = DepartmentState()
        state.add_modal_open = True
        with _as_admin(state):
            text = await _run(
                state.create_department,
                {"name": " Informationstechnik ", "abbreviation": " IT "},
            )
        created = repo.create.await_args.args[1]
        assert (created.name, created.abbreviation) == ("Informationstechnik", "IT")
        assert "erstellt" in text
        assert state.add_modal_open is False

    async def test_create_duplicate_shows_message(self, repo: AsyncMock) -> None:
        repo.create = AsyncMock(side_effect=IntegrityError("x", {}, Exception()))
        state = DepartmentState()
        with _as_admin(state):
            text = await _run(
                state.create_department, {"name": "IT", "abbreviation": "IT"}
            )
        assert "bereits vergeben" in text

    async def test_create_rejects_missing_abbreviation(self, repo: AsyncMock) -> None:
        state = DepartmentState()
        with _as_admin(state):
            text = await _run(state.create_department, {"name": "IT"})
        assert "Kürzel angeben" in text
        repo.create.assert_not_awaited()

    async def test_create_persists_highlight_flag(self, repo: AsyncMock) -> None:
        state = DepartmentState()
        with _as_admin(state):
            await _run(
                state.create_department,
                {
                    "name": "Informationstechnik",
                    "abbreviation": "IT",
                    "highlighted": "on",
                },
            )
        assert repo.create.await_args.args[1].highlighted is True

    async def test_select_and_update(self, repo: AsyncMock) -> None:
        entity = _entity()
        repo.find_by_id = AsyncMock(return_value=entity)
        state = DepartmentState()
        with _as_admin(state):
            await _run(state.select_department_and_open_edit, 3)
            assert state.edit_modal_open is True
            text = await _run(
                state.update_department, {"name": "IT-Services", "abbreviation": "ITS"}
            )
        assert (entity.name, entity.abbreviation) == ("IT-Services", "ITS")
        assert "aktualisiert" in text
        assert state.edit_modal_open is False
        assert state.selected_department is None

    async def test_update_without_selection(self, repo: AsyncMock) -> None:
        state = DepartmentState()
        with _as_admin(state):
            text = await _run(
                state.update_department, {"name": "IT", "abbreviation": "IT"}
            )
        assert "Keine Abteilung" in text
        repo.update.assert_not_awaited()

    async def test_delete(self, repo: AsyncMock) -> None:
        repo.delete_by_id = AsyncMock(return_value=True)
        state = DepartmentState()
        with _as_admin(state):
            text = await _run(state.delete_department, 3)
        assert "gelöscht" in text

    async def test_delete_unknown(self, repo: AsyncMock) -> None:
        repo.delete_by_id = AsyncMock(return_value=False)
        state = DepartmentState()
        with _as_admin(state):
            text = await _run(state.delete_department, 3)
        assert "nicht gefunden" in text


class TestDepartmentComponents:
    def test_table_renders(self) -> None:
        rendered = str(departments_table())
        assert "filtered_departments" in rendered

    def test_toolbar_has_search_and_add(self) -> None:
        assert len(departments_toolbar()) == 2

    def test_form_inputs_limit_length_in_browser(self) -> None:
        rendered = str(department_form_fields())
        assert "maxLength:255" in rendered
        assert "maxLength:10" in rendered
        assert '["maxLength"]' not in rendered
