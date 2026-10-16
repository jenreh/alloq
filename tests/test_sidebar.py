"""Tests for the app sidebar and its state."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from alloq_dashboard.states import RoleCapacityState

from app.components import sidebar_state
from app.components.sidebar import (
    ADMIN_ITEMS,
    PLANNING_ITEMS,
    _brand,
    _user_menu,
    is_route_active,
    sidebar,
)
from app.components.sidebar_state import SidebarState

MODULE = "app.components.sidebar_state"


class _FakeLogin:
    def __init__(self, user: Any) -> None:
        self._user = user

    @property
    async def authenticated_user(self) -> Any:
        return self._user

    async def redir(self) -> None:
        return None


USER = SimpleNamespace(user_id=1, is_admin=True, email="ada@example.com")


def _state(*, is_admin: bool = True) -> SidebarState:
    state = SidebarState()
    user = SimpleNamespace(**{**vars(USER), "is_admin": is_admin})
    object.__setattr__(state, "get_state", AsyncMock(return_value=_FakeLogin(user)))
    return state


def _session(counts: list[int]) -> Any:
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[MagicMock(scalar_one=lambda c=c: c) for c in counts]
    )

    @asynccontextmanager
    async def _ctx() -> AsyncIterator[MagicMock]:
        yield session

    return _ctx, session


async def _run(state: SidebarState) -> None:
    async for _ in state.load():
        pass


class TestSidebarStateLoad:
    async def test_load_counts_open_projects_and_employees(self) -> None:
        state = _state()
        ctx, session = _session([3, 2])
        with patch(f"{MODULE}.get_asyncdb_session", ctx):
            await _run(state)
        assert state.project_count == 3
        assert state.employee_count == 2
        statements = [str(c.args[0]) for c in session.execute.call_args_list]
        assert "count" in statements[0].lower()
        assert "state" in statements[0]
        assert "employees" in statements[1]

    async def test_recent_data_is_not_reloaded(self) -> None:
        state = _state()
        state._loaded_at = sidebar_state.time.monotonic()
        ctx, session = _session([])
        with patch(f"{MODULE}.get_asyncdb_session", ctx):
            await _run(state)
        session.execute.assert_not_called()

    async def test_invalidate_forces_reload(self) -> None:
        state = _state()
        state._loaded_at = sidebar_state.time.monotonic()
        state.invalidate()
        assert state._loaded_at == 0.0

    async def test_non_admin_is_refused(self) -> None:
        state = _state(is_admin=False)
        ctx, session = _session([])
        with patch(f"{MODULE}.get_asyncdb_session", ctx):
            await _run(state)
        session.execute.assert_not_called()


class TestSidebarComponent:
    def test_brand_icon_uses_theme_surface_background(self) -> None:
        assert "var(--aq-surface)" in str(_brand())

    def test_user_menu_exposes_color_mode_options(self) -> None:
        rendered = str(_user_menu())
        assert "Darstellung" in rendered
        assert "Dunkel" in rendered
        assert "Hell" in rendered
        assert "System" in rendered

    def test_renders_navigation_entries(self) -> None:
        rendered = str(sidebar())
        for route, label, _icon in (*PLANNING_ITEMS, *ADMIN_ITEMS):
            assert json.dumps(label)[1:-1] in rendered
            assert route in rendered
        assert "Freie Kapazit" in rendered
        assert "Meine Projekte" not in rendered
        assert RoleCapacityState.get_name() in rendered
        assert 'fz:"11px"' in rendered
        assert "decimalScale:1" in rendered
        assert "fixedDecimalScale:true" in rendered
        assert "aq-sidebar" in rendered
        assert "data-tauri-drag-region" in rendered
        assert "LucidePanelLeftClose" in rendered

    def test_index_route_matches_both_paths(self) -> None:
        rendered = str(is_route_active("/"))
        assert '"/index"' in rendered
        assert '"/"' in rendered

    def test_homepage_highlights_planning_navigation(self) -> None:
        rendered = str(is_route_active("/plan"))
        assert '"/plan"' in rendered
        assert '"/"' in rendered
        assert '"/index"' in rendered

    def test_other_routes_match_exactly(self) -> None:
        assert '"/projects"' in str(is_route_active("/projects"))
