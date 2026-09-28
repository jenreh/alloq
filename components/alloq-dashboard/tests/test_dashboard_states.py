"""Tests for dashboard substate cache TTL and load lifecycle."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from alloq_dashboard.models import ProjectsOverviewKpi, RiskKpi
from alloq_dashboard.states.dashboard_states import (
    CACHE_TTL_SECONDS,
    LOAD_ERROR_MESSAGE,
    DashboardState,
    ProjectsOverviewState,
    RiskState,
    _is_fresh,
    _ts_now,
)

from appkit_user.authentication.backend.models import User

_LOADER = "alloq_dashboard.states.dashboard_states.aggregation.load_projects_overview"
_ADMIN = User(user_id=1, name="Admin", is_admin=True)
_MEMBER = User(user_id=2, name="Member", is_admin=False)


def _load_fn(state_cls: type) -> Callable[..., Coroutine[Any, Any, None]]:
    """The background ``load`` coroutine, driven directly in tests."""
    return cast("Any", state_cls).load.fn


class _FakeLoginState:
    def __init__(self, user: User | None) -> None:
        self._user = user

    @property
    def authenticated_user(self) -> Any:
        async def _get() -> User | None:
            return self._user

        return _get()


def _login_as(state_cls: type, user: User | None) -> Any:
    return patch.object(
        state_cls, "get_state", new=AsyncMock(return_value=_FakeLoginState(user))
    )


@pytest.fixture
def as_admin() -> Iterator[None]:
    with _login_as(ProjectsOverviewState, _ADMIN):
        yield


def test_is_fresh_returns_false_for_empty() -> None:
    assert _is_fresh("") is False


def test_is_fresh_returns_false_for_invalid() -> None:
    assert _is_fresh("not-a-timestamp") is False


def test_is_fresh_returns_true_within_ttl() -> None:
    recent = (datetime.now(tz=UTC) - timedelta(seconds=5)).isoformat()
    assert _is_fresh(recent) is True


def test_is_fresh_returns_false_after_ttl() -> None:
    expired = (
        datetime.now(tz=UTC) - timedelta(seconds=CACHE_TTL_SECONDS + 60)
    ).isoformat()
    assert _is_fresh(expired) is False


def test_ts_now_round_trip() -> None:
    iso = _ts_now()
    parsed = datetime.fromisoformat(iso)
    assert (datetime.now(tz=UTC) - parsed).total_seconds() < 5


@pytest.mark.asyncio
@pytest.mark.usefixtures("as_admin")
async def test_projects_overview_load_populates_data() -> None:
    payload = ProjectsOverviewKpi(total=3, active=2, planned=1)
    state = ProjectsOverviewState()
    with patch(
        _LOADER,
        new=AsyncMock(return_value=payload),
    ):
        # Background events: drive the underlying coroutine directly.
        await _load_fn(ProjectsOverviewState)(state, force=True)
    assert state.data.total == 3
    assert state.data.active == 2
    assert state.is_loading is False
    assert state.last_loaded != ""


@pytest.mark.asyncio
@pytest.mark.usefixtures("as_admin")
async def test_projects_overview_load_skips_when_fresh() -> None:
    state = ProjectsOverviewState()
    state.last_loaded = _ts_now()
    state.data = ProjectsOverviewKpi(total=99)
    mock = AsyncMock(return_value=ProjectsOverviewKpi(total=0))
    with patch(
        _LOADER,
        new=mock,
    ):
        await _load_fn(ProjectsOverviewState)(state)
    mock.assert_not_called()
    assert state.data.total == 99


@pytest.mark.asyncio
@pytest.mark.usefixtures("as_admin")
async def test_projects_overview_load_records_error() -> None:
    state = ProjectsOverviewState()
    boom = AsyncMock(side_effect=RuntimeError("db down"))
    with patch(
        _LOADER,
        new=boom,
    ):
        await _load_fn(ProjectsOverviewState)(state, force=True)
    assert state.is_loading is False
    assert state.error_message == LOAD_ERROR_MESSAGE
    assert "db down" not in state.error_message


@pytest.mark.asyncio
@pytest.mark.parametrize("user", [_MEMBER, None])
async def test_card_load_rejects_non_admin(user: User | None) -> None:
    state = ProjectsOverviewState()
    loader = AsyncMock(return_value=ProjectsOverviewKpi(total=7))
    with _login_as(ProjectsOverviewState, user), patch(_LOADER, new=loader):
        await _load_fn(ProjectsOverviewState)(state, force=True)
    loader.assert_not_called()
    assert state.data.total == 0
    assert state.last_loaded == ""


@pytest.mark.asyncio
async def test_risk_load_rejects_non_admin() -> None:
    state = RiskState()
    loader = AsyncMock(return_value=RiskKpi(open_total=5))
    with (
        _login_as(RiskState, _MEMBER),
        patch(
            "alloq_dashboard.states.dashboard_states.aggregation.load_risks",
            new=loader,
        ),
    ):
        await _load_fn(RiskState)(state, force=True)
    loader.assert_not_called()
    assert state.data.open_total == 0


@pytest.mark.asyncio
async def test_load_all_rejects_non_admin() -> None:
    state = DashboardState()
    with _login_as(DashboardState, _MEMBER):
        result = await DashboardState.load_all.fn(state)
    assert not isinstance(result, list)


@pytest.mark.asyncio
async def test_load_all_returns_card_loads_for_admin() -> None:
    state = DashboardState()
    with _login_as(DashboardState, _ADMIN):
        result = await DashboardState.load_all.fn(state)
    assert isinstance(result, list)
    assert RiskState.load in result


@pytest.mark.asyncio
@pytest.mark.usefixtures("as_admin")
async def test_superseded_load_does_not_overwrite_newer_result() -> None:
    state = ProjectsOverviewState()
    release_slow = asyncio.Event()

    async def slow_then_fast() -> ProjectsOverviewKpi:
        if not release_slow.is_set():
            release_slow.set()
            await asyncio.sleep(0.05)
            return ProjectsOverviewKpi(total=1)  # stale snapshot
        return ProjectsOverviewKpi(total=2)

    with patch(_LOADER, new=slow_then_fast):
        slow = asyncio.create_task(_load_fn(ProjectsOverviewState)(state, force=True))
        await release_slow.wait()
        await _load_fn(ProjectsOverviewState)(state, force=True)
        await slow
    assert state.data.total == 2
