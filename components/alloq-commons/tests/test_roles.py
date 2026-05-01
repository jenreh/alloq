"""Tests for organizational role management."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import reflex as rx
from alloq_commons.components.role import (
    add_role_button,
    add_role_modal,
    edit_role_modal,
    roles_table,
)
from alloq_commons.entities.role import RoleEntity
from alloq_commons.models.role import Role, RoleCreate
from alloq_commons.repositories.role_repository import RoleRepository
from alloq_commons.state.role_states import RoleState
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

# ============================================================================
# Entity Tests
# ============================================================================


class TestRoleEntity:
    """Tests for the RoleEntity database model."""

    def test_create_entity(self) -> None:
        entity = RoleEntity(name="Developer", description="A software developer")
        assert entity.name == "Developer"
        assert entity.description == "A software developer"

    def test_create_entity_without_description(self) -> None:
        entity = RoleEntity(name="Tester")
        assert entity.name == "Tester"
        assert entity.description is None

    def test_to_dict(self) -> None:
        entity = RoleEntity(name="Designer", description="UI/UX Designer")
        entity.id = 1
        entity.created = None
        entity.updated = None
        result = entity.to_dict()
        assert result["id"] == 1
        assert result["name"] == "Designer"
        assert result["description"] == "UI/UX Designer"

    def test_to_dict_empty_description(self) -> None:
        entity = RoleEntity(name="Lead")
        entity.id = 2
        entity.created = None
        entity.updated = None
        entity.description = None
        result = entity.to_dict()
        assert result["description"] == ""

    def test_tablename(self) -> None:
        assert RoleEntity.__tablename__ == "roles"


# ============================================================================
# Model Tests
# ============================================================================


class TestRoleModel:
    """Tests for the Role Pydantic model."""

    def test_defaults(self) -> None:
        role = Role()
        assert role.id == 0
        assert role.name == ""
        assert role.description == ""
        assert role.created is None
        assert role.updated is None

    def test_from_dict(self) -> None:
        role = Role(id=1, name="Tester", description="QA Engineer")
        assert role.id == 1
        assert role.name == "Tester"
        assert role.description == "QA Engineer"


class TestRoleCreateModel:
    """Tests for the RoleCreate Pydantic model."""

    def test_valid_role(self) -> None:
        role = RoleCreate(name="Developer", description="Builds software")
        assert role.name == "Developer"
        assert role.description == "Builds software"

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            RoleCreate(description="No name")  # type: ignore[call-arg]

    def test_max_length_name(self) -> None:
        long_name = "x" * 256
        with pytest.raises(ValidationError):
            RoleCreate(name=long_name)

    def test_max_length_boundary(self) -> None:
        name_255 = "x" * 255
        role = RoleCreate(name=name_255)
        assert len(role.name) == 255

    def test_empty_description_default(self) -> None:
        role = RoleCreate(name="Test")
        assert role.description == ""


# ============================================================================
# Repository Tests
# ============================================================================


class TestRoleRepository:
    """Tests for the RoleRepository async operations."""

    @pytest.fixture
    def repo(self) -> RoleRepository:
        return RoleRepository()

    @pytest.mark.asyncio
    async def test_find_all_paginated(self, async_session: AsyncSession) -> None:
        repo = RoleRepository()
        # Seed data
        entity1 = RoleEntity(name="Alpha", description="First")
        entity2 = RoleEntity(name="Beta", description="Second")
        async_session.add(entity1)
        async_session.add(entity2)
        await async_session.flush()

        results = await repo.find_all_paginated(async_session, limit=10, offset=0)
        assert len(results) == 2
        # Ordered by name
        assert results[0].name == "Alpha"
        assert results[1].name == "Beta"

    @pytest.mark.asyncio
    async def test_find_all_paginated_with_offset(
        self, async_session: AsyncSession
    ) -> None:
        repo = RoleRepository()
        for i in range(5):
            async_session.add(RoleEntity(name=f"Role_{i:02d}"))
        await async_session.flush()

        results = await repo.find_all_paginated(async_session, limit=2, offset=2)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_create(self, async_session: AsyncSession) -> None:
        repo = RoleRepository()
        entity = RoleEntity(name="Architect", description="System design")
        created = await repo.create(async_session, entity)
        assert created.id is not None
        assert created.name == "Architect"
        assert created.description == "System design"

    @pytest.mark.asyncio
    async def test_create_no_description(self, async_session: AsyncSession) -> None:
        repo = RoleRepository()
        entity = RoleEntity(name="Intern")
        created = await repo.create(async_session, entity)
        assert created.name == "Intern"
        assert created.description is None

    @pytest.mark.asyncio
    async def test_update(self, async_session: AsyncSession) -> None:
        repo = RoleRepository()
        entity = RoleEntity(name="Old Name", description="Old desc")
        await repo.create(async_session, entity)

        entity.name = "New Name"
        entity.description = "New desc"
        updated = await repo.update(async_session, entity)
        assert updated.name == "New Name"
        assert updated.description == "New desc"

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, async_session: AsyncSession) -> None:
        repo = RoleRepository()
        result = await repo.find_by_id(async_session, 9999)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_by_id(self, async_session: AsyncSession) -> None:
        repo = RoleRepository()
        entity = RoleEntity(name="ToDelete")
        async_session.add(entity)
        await async_session.flush()
        role_id = entity.id

        deleted = await repo.delete_by_id(async_session, role_id)
        assert deleted is True

        found = await repo.find_by_id(async_session, role_id)
        assert found is None


# ============================================================================
# State Tests
# ============================================================================


class TestRoleState:
    """Tests for the RoleState Reflex state class."""

    def test_initial_state(self) -> None:
        state = RoleState()  # type: ignore[call-arg]
        assert state.roles == []
        assert state.selected_role is None
        assert state.is_loading is False
        assert state.add_modal_open is False
        assert state.edit_modal_open is False
        assert state.search_filter == ""

    def test_set_search_filter(self) -> None:
        state = RoleState()  # type: ignore[call-arg]
        state.set_search_filter("dev")
        assert state.search_filter == "dev"

    def test_open_close_add_modal(self) -> None:
        state = RoleState()  # type: ignore[call-arg]
        state.open_add_modal()
        assert state.add_modal_open is True
        state.close_add_modal()
        assert state.add_modal_open is False

    def test_open_close_edit_modal(self) -> None:
        state = RoleState()  # type: ignore[call-arg]
        state.selected_role = Role(id=1, name="Test")
        state.open_edit_modal()
        assert state.edit_modal_open is True
        state.close_edit_modal()
        assert state.edit_modal_open is False
        assert state.selected_role is None

    def test_filtered_roles_no_filter(self) -> None:
        state = RoleState()  # type: ignore[call-arg]
        state.roles = [
            Role(id=1, name="Developer"),
            Role(id=2, name="Designer"),
        ]
        state.search_filter = ""
        result = state.filtered_roles
        assert len(result) == 2

    def test_filtered_roles_by_name(self) -> None:
        state = RoleState()  # type: ignore[call-arg]
        state.roles = [
            Role(id=1, name="Developer", description="Builds apps"),
            Role(id=2, name="Designer", description="Creates UX"),
        ]
        state.search_filter = "dev"
        result = state.filtered_roles
        assert len(result) == 1
        assert result[0].name == "Developer"

    def test_filtered_roles_by_description(self) -> None:
        state = RoleState()  # type: ignore[call-arg]
        state.roles = [
            Role(id=1, name="Developer", description="Builds apps"),
            Role(id=2, name="Designer", description="Creates UX"),
        ]
        state.search_filter = "ux"
        result = state.filtered_roles
        assert len(result) == 1
        assert result[0].name == "Designer"

    def test_filtered_roles_case_insensitive(self) -> None:
        state = RoleState()  # type: ignore[call-arg]
        state.roles = [
            Role(id=1, name="Developer"),
            Role(id=2, name="DESIGNER"),
        ]
        state.search_filter = "DESIGNER"
        result = state.filtered_roles
        assert len(result) == 1


# ============================================================================
# Async State Tests (DB operations)
# ============================================================================


def _mock_session_ctx(session: AsyncMock):
    """Create an async context manager mock for get_asyncdb_session."""

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx


def _authenticated_state() -> RoleState:
    """Create a RoleState with mocked authentication."""
    state = RoleState()  # type: ignore[call-arg]
    return state


@asynccontextmanager
async def _patch_auth(state: RoleState):
    """Patch get_state on the state instance to bypass auth decorator."""
    login_state = MagicMock()
    # is_authenticated is awaited in the decorator, so make it a coroutine
    login_state.is_authenticated = AsyncMock(return_value=True)()
    original_get_state = type(state).get_state
    object.__setattr__(state, "get_state", AsyncMock(return_value=login_state))
    try:
        yield
    finally:
        object.__setattr__(state, "get_state", original_get_state)


class TestRoleStateAsync:
    """Tests for async RoleState methods with mocked DB sessions."""

    @pytest.mark.asyncio
    async def test_select_role_loads_entity(self) -> None:
        state = RoleState()  # type: ignore[call-arg]
        entity = RoleEntity(name="Dev", description="Developer")
        entity.id = 42
        entity.created = None
        entity.updated = None

        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=entity)

        with (
            patch(
                "alloq_commons.state.role_states.get_asyncdb_session",
                _mock_session_ctx(session),
            ),
            patch(
                "alloq_commons.state.role_states.role_repo",
                mock_repo,
            ),
        ):
            await state._select_role(42)

        assert state.selected_role is not None
        assert state.selected_role.id == 42
        assert state.selected_role.name == "Dev"

    @pytest.mark.asyncio
    async def test_select_role_not_found(self) -> None:
        state = RoleState()  # type: ignore[call-arg]
        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=None)

        with (
            patch(
                "alloq_commons.state.role_states.get_asyncdb_session",
                _mock_session_ctx(session),
            ),
            patch(
                "alloq_commons.state.role_states.role_repo",
                mock_repo,
            ),
        ):
            await state._select_role(999)

        assert state.selected_role is None

    @pytest.mark.asyncio
    async def test_select_role_and_open_edit(self) -> None:
        state = RoleState()  # type: ignore[call-arg]
        entity = RoleEntity(name="QA", description="Tester")
        entity.id = 7
        entity.created = None
        entity.updated = None

        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=entity)

        with (
            patch(
                "alloq_commons.state.role_states.get_asyncdb_session",
                _mock_session_ctx(session),
            ),
            patch(
                "alloq_commons.state.role_states.role_repo",
                mock_repo,
            ),
        ):
            await state.select_role_and_open_edit(7)

        assert state.selected_role is not None
        assert state.edit_modal_open is True

    @pytest.mark.asyncio
    async def test_load_roles_internal(self) -> None:
        state = RoleState()  # type: ignore[call-arg]
        entities = [
            RoleEntity(name="Alpha", description="First"),
            RoleEntity(name="Beta", description="Second"),
        ]
        for i, e in enumerate(entities, start=1):
            e.id = i
            e.created = None
            e.updated = None

        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_all_paginated = AsyncMock(return_value=entities)

        with (
            patch(
                "alloq_commons.state.role_states.get_asyncdb_session",
                _mock_session_ctx(session),
            ),
            patch(
                "alloq_commons.state.role_states.role_repo",
                mock_repo,
            ),
        ):
            await state._load_roles()

        assert len(state.roles) == 2
        assert state.roles[0].name == "Alpha"

    @pytest.mark.asyncio
    async def test_load_roles_authenticated(self) -> None:
        state = _authenticated_state()
        entities = [RoleEntity(name="Gamma", description="Third")]
        entities[0].id = 3
        entities[0].created = None
        entities[0].updated = None

        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_all_paginated = AsyncMock(return_value=entities)

        async with _patch_auth(state):
            with (
                patch(
                    "alloq_commons.state.role_states.get_asyncdb_session",
                    _mock_session_ctx(session),
                ),
                patch(
                    "alloq_commons.state.role_states.role_repo",
                    mock_repo,
                ),
            ):
                results = []
                async for item in state.load_roles():
                    results.append(item)

        assert state.is_loading is False
        assert len(state.roles) == 1

    @pytest.mark.asyncio
    async def test_create_role_success(self) -> None:
        state = _authenticated_state()
        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock()
        mock_repo.find_all_paginated = AsyncMock(return_value=[])

        async with _patch_auth(state):
            with (
                patch(
                    "alloq_commons.state.role_states.get_asyncdb_session",
                    _mock_session_ctx(session),
                ),
                patch(
                    "alloq_commons.state.role_states.role_repo",
                    mock_repo,
                ),
            ):
                results = []
                async for item in state.create_role(
                    {"name": "NewRole", "description": "Desc"}
                ):
                    results.append(item)

        assert state.is_loading is False
        assert state.add_modal_open is False
        mock_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_role_error(self) -> None:
        state = _authenticated_state()
        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(side_effect=RuntimeError("DB error"))

        async with _patch_auth(state):
            with (
                patch(
                    "alloq_commons.state.role_states.get_asyncdb_session",
                    _mock_session_ctx(session),
                ),
                patch(
                    "alloq_commons.state.role_states.role_repo",
                    mock_repo,
                ),
            ):
                results = []
                async for item in state.create_role(
                    {"name": "FailRole", "description": ""}
                ):
                    results.append(item)

        assert state.is_loading is False

    @pytest.mark.asyncio
    async def test_update_role_success(self) -> None:
        state = _authenticated_state()
        state.selected_role = Role(id=5, name="Old", description="OldDesc")

        entity = RoleEntity(name="Old", description="OldDesc")
        entity.id = 5
        entity.created = None
        entity.updated = None

        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=entity)
        mock_repo.update = AsyncMock(return_value=entity)
        mock_repo.find_all_paginated = AsyncMock(return_value=[])

        async with _patch_auth(state):
            with (
                patch(
                    "alloq_commons.state.role_states.get_asyncdb_session",
                    _mock_session_ctx(session),
                ),
                patch(
                    "alloq_commons.state.role_states.role_repo",
                    mock_repo,
                ),
            ):
                results = []
                async for item in state.update_role(
                    {"name": "Updated", "description": "NewDesc"}
                ):
                    results.append(item)

        assert state.is_loading is False
        assert state.edit_modal_open is False
        mock_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_role_no_selection(self) -> None:
        state = _authenticated_state()
        state.selected_role = None

        async with _patch_auth(state):
            with patch(
                "alloq_commons.state.role_states.get_asyncdb_session",
                _mock_session_ctx(AsyncMock()),
            ):
                results = []
                async for item in state.update_role({"name": "X", "description": ""}):
                    results.append(item)

        assert state.is_loading is False

    @pytest.mark.asyncio
    async def test_update_role_not_found(self) -> None:
        state = _authenticated_state()
        state.selected_role = Role(id=99, name="Ghost")

        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=None)

        async with _patch_auth(state):
            with (
                patch(
                    "alloq_commons.state.role_states.get_asyncdb_session",
                    _mock_session_ctx(session),
                ),
                patch(
                    "alloq_commons.state.role_states.role_repo",
                    mock_repo,
                ),
            ):
                results = []
                async for item in state.update_role({"name": "X", "description": ""}):
                    results.append(item)

        assert state.is_loading is False

    @pytest.mark.asyncio
    async def test_update_role_error(self) -> None:
        state = _authenticated_state()
        state.selected_role = Role(id=5, name="Old")

        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(side_effect=RuntimeError("DB error"))

        async with _patch_auth(state):
            with (
                patch(
                    "alloq_commons.state.role_states.get_asyncdb_session",
                    _mock_session_ctx(session),
                ),
                patch(
                    "alloq_commons.state.role_states.role_repo",
                    mock_repo,
                ),
            ):
                results = []
                async for item in state.update_role({"name": "X", "description": ""}):
                    results.append(item)

        assert state.is_loading is False

    @pytest.mark.asyncio
    async def test_delete_role_success(self) -> None:
        state = _authenticated_state()
        entity = RoleEntity(name="ToDelete")
        entity.id = 10
        entity.created = None
        entity.updated = None

        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=entity)
        mock_repo.delete_by_id = AsyncMock(return_value=True)
        mock_repo.find_all_paginated = AsyncMock(return_value=[])

        async with _patch_auth(state):
            with (
                patch(
                    "alloq_commons.state.role_states.get_asyncdb_session",
                    _mock_session_ctx(session),
                ),
                patch(
                    "alloq_commons.state.role_states.role_repo",
                    mock_repo,
                ),
            ):
                results = []
                async for item in state.delete_role(10):
                    results.append(item)

        assert state.is_loading is False
        mock_repo.delete_by_id.assert_called_once_with(session, 10)

    @pytest.mark.asyncio
    async def test_delete_role_not_found(self) -> None:
        state = _authenticated_state()
        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=None)

        async with _patch_auth(state):
            with (
                patch(
                    "alloq_commons.state.role_states.get_asyncdb_session",
                    _mock_session_ctx(session),
                ),
                patch(
                    "alloq_commons.state.role_states.role_repo",
                    mock_repo,
                ),
            ):
                results = []
                async for item in state.delete_role(999):
                    results.append(item)

        assert state.is_loading is False

    @pytest.mark.asyncio
    async def test_delete_role_delete_fails(self) -> None:
        state = _authenticated_state()
        entity = RoleEntity(name="Stuck")
        entity.id = 11
        entity.created = None
        entity.updated = None

        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=entity)
        mock_repo.delete_by_id = AsyncMock(return_value=False)

        async with _patch_auth(state):
            with (
                patch(
                    "alloq_commons.state.role_states.get_asyncdb_session",
                    _mock_session_ctx(session),
                ),
                patch(
                    "alloq_commons.state.role_states.role_repo",
                    mock_repo,
                ),
            ):
                results = []
                async for item in state.delete_role(11):
                    results.append(item)

        assert state.is_loading is False

    @pytest.mark.asyncio
    async def test_delete_role_error(self) -> None:
        state = _authenticated_state()
        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(side_effect=RuntimeError("DB error"))

        async with _patch_auth(state):
            with (
                patch(
                    "alloq_commons.state.role_states.get_asyncdb_session",
                    _mock_session_ctx(session),
                ),
                patch(
                    "alloq_commons.state.role_states.role_repo",
                    mock_repo,
                ),
            ):
                results = []
                async for item in state.delete_role(1):
                    results.append(item)

        assert state.is_loading is False


# ============================================================================
# Component Tests
# ============================================================================


class TestRoleComponents:
    """Basic tests for role UI components."""

    def test_roles_table_returns_component(self) -> None:
        result = roles_table()
        assert isinstance(result, rx.Component)

    def test_add_role_modal_returns_component(self) -> None:
        result = add_role_modal()
        assert isinstance(result, rx.Component)

    def test_edit_role_modal_returns_component(self) -> None:
        result = edit_role_modal()
        assert isinstance(result, rx.Component)

    def test_add_role_button_returns_component(self) -> None:
        result = add_role_button()
        assert isinstance(result, rx.Component)
