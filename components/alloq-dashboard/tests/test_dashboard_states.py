"""Tests for dashboard substate cache TTL and load lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from alloq_dashboard.models import ProjectsOverviewKpi
from alloq_dashboard.states.dashboard_states import (
    CACHE_TTL_SECONDS,
    ProjectsOverviewState,
    _is_fresh,
    _ts_now,
)


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
async def test_projects_overview_load_populates_data() -> None:
    payload = ProjectsOverviewKpi(total=3, active=2, planned=1)
    state = ProjectsOverviewState()
    with patch(
        "alloq_dashboard.states.dashboard_states.aggregation.load_projects_overview",
        new=AsyncMock(return_value=payload),
    ):
        # Background events: drive the underlying coroutine directly.
        await ProjectsOverviewState.load.fn(state, force=True)
    assert state.data.total == 3
    assert state.data.active == 2
    assert state.is_loading is False
    assert state.last_loaded != ""


@pytest.mark.asyncio
async def test_projects_overview_load_skips_when_fresh() -> None:
    state = ProjectsOverviewState()
    state.last_loaded = _ts_now()
    state.data = ProjectsOverviewKpi(total=99)
    mock = AsyncMock(return_value=ProjectsOverviewKpi(total=0))
    with patch(
        "alloq_dashboard.states.dashboard_states.aggregation.load_projects_overview",
        new=mock,
    ):
        await ProjectsOverviewState.load.fn(state)
    mock.assert_not_called()
    assert state.data.total == 99


@pytest.mark.asyncio
async def test_projects_overview_load_records_error() -> None:
    state = ProjectsOverviewState()
    boom = AsyncMock(side_effect=RuntimeError("db down"))
    with patch(
        "alloq_dashboard.states.dashboard_states.aggregation.load_projects_overview",
        new=boom,
    ):
        await ProjectsOverviewState.load.fn(state, force=True)
    assert state.is_loading is False
    assert "db down" in state.error_message
