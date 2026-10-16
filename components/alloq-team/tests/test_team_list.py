"""Team list: utilization overview, filter, inspector and rendering."""

from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_commons.models.employee import Absence, Employee
from alloq_team.components.employee_table import employee_list, employee_table
from alloq_team.components.toolbar import team_filter, team_toolbar
from alloq_team.services import team_overview as service
from alloq_team.services.team_overview import (
    Allocation,
    ProjectInfo,
    TeamOverview,
    build_overview,
    week_starts,
)
from alloq_team.states.team_list_state import load_tone, to_detail
from alloq_team.states.team_state import TeamState

MONDAY = date(2026, 10, 12)
WEEKS = week_starts(MONDAY, 4)
PROJECTS = {
    1: ProjectInfo(id=1, name="Alpha", color="#2E6BD6"),
    2: ProjectInfo(id=2, name="Beta", color="#3D9A5E"),
}


def _employee(eid: int, **kwargs: Any) -> Employee:
    data = {"id": eid, "first_name": f"P{eid}", "last_name": "X", "internal_hours": 0}
    return Employee(**{**data, **kwargs})


def _alloc(eid: int, pid: int, week: int, days: float) -> Allocation:
    return Allocation(
        project_id=pid, employee_id=eid, week_start=WEEKS[week], person_days=days
    )


class TestBuildOverview:
    def test_week_starts_begin_on_monday(self) -> None:
        assert week_starts(date(2026, 10, 15), 2) == [MONDAY, date(2026, 10, 19)]

    def test_full_week_is_100_percent(self) -> None:
        overview = build_overview(
            [_employee(1)], [_alloc(1, 1, 0, 5.0)], PROJECTS, WEEKS
        )[1]
        assert overview.load_percent == 100
        assert [w.percent for w in overview.weeks] == [100, 0, 0, 0]
        assert overview.free_days == 15.0
        assert overview.free is True
        assert overview.overloaded is False

    def test_assignments_sum_days_per_project(self) -> None:
        allocations = [
            _alloc(1, 1, 0, 2.0),
            _alloc(1, 1, 1, 2.0),
            _alloc(1, 2, 0, 1.0),
            _alloc(1, 9, 0, 3.0),  # completed project: ignored
        ]
        overview = build_overview([_employee(1)], allocations, PROJECTS, WEEKS)[1]
        assert [(a.name, a.days) for a in overview.assignments] == [
            ("Alpha", 4.0),
            ("Beta", 1.0),
        ]
        assert overview.load_percent == 60

    def test_overload(self) -> None:
        overview = build_overview(
            [_employee(1)], [_alloc(1, 1, 0, 7.0)], PROJECTS, WEEKS
        )[1]
        assert overview.overloaded is True

    def test_absence_this_week(self) -> None:
        absent = _employee(
            1,
            absences=[Absence(start_date=MONDAY, end_date=date(2026, 10, 16))],
        )
        overview = build_overview([absent], [], PROJECTS, WEEKS)[1]
        assert overview.absent_now is True
        assert overview.weeks[0].absent is True

    def test_no_weeks(self) -> None:
        assert build_overview([_employee(1)], [], PROJECTS, []) == {}


class TestDetail:
    def test_load_tone(self) -> None:
        assert load_tone(None) == "neutral"
        assert load_tone(TeamOverview(employee_id=1, load_percent=120)) == "negative"
        assert load_tone(TeamOverview(employee_id=1, load_percent=90)) == "warning"
        assert load_tone(TeamOverview(employee_id=1, load_percent=40)) == "positive"
        assert (
            load_tone(TeamOverview(employee_id=1, load_percent=0, absent_now=True))
            == "neutral"
        )

    def test_to_detail(self) -> None:
        employee = _employee(
            3,
            first_name="Ada",
            last_name="Lovelace",
            job_title="Engineer",
            role_names=["Dev", "Ops"],
            absences=[Absence(start_date=MONDAY, end_date=date(2026, 10, 16))],
        )
        detail = to_detail(employee, TeamOverview(employee_id=3, load_percent=50))
        assert detail.name == "Ada Lovelace"
        assert detail.initials == "AL"
        assert detail.subtitle == "Engineer"
        assert detail.role == "Dev"
        assert detail.roles == "Dev, Ops"
        assert detail.absences == ["12.10.2026 – 16.10.2026"]
        assert detail.load_tone == "positive"

    def test_to_detail_without_overview(self) -> None:
        detail = to_detail(_employee(1), None)
        assert detail.load_percent == 0
        assert detail.weeks == []


def _state() -> TeamState:
    state = TeamState()
    state.current_employee_id = 9
    state.employees = [
        _employee(1, manager_id=9),
        _employee(2),
        _employee(3),
    ]
    state.overviews = {
        1: TeamOverview(employee_id=1, load_percent=120),
        2: TeamOverview(employee_id=2, load_percent=20, free_days=10),
        3: TeamOverview(employee_id=3, load_percent=100),
    }
    return state


class TestTeamListState:
    def test_groups(self) -> None:
        state = _state()
        assert [r.id for r in state.mine_rows] == [1]
        assert [r.id for r in state.other_rows] == [2, 3]
        assert state.row_count == 3

    def test_visible_total_free_days_sums_visible_rows(self) -> None:
        state = _state()
        state.overviews[1].free_days = 1.2
        state.overviews[2].free_days = 10.5
        state.overviews[3].free_days = 2.3

        assert state.visible_total_free_days == 14.0

        state.set_list_filter("Überlastet")
        assert state.visible_total_free_days == 1.2

        state.set_list_filter("Meine")
        assert state.visible_total_free_days == 1.2

    def test_sort_defaults_and_toggles(self) -> None:
        state = _state()

        assert state.sort_column == "name"
        assert state.sort_desc is False

        state.toggle_sort("hours")
        assert state.sort_column == "hours"
        assert state.sort_desc is False

        state.toggle_sort("hours")
        assert state.sort_desc is True

        state.toggle_sort("role")
        assert state.sort_column == "role"
        assert state.sort_desc is False

        state.toggle_sort("unknown")
        assert state.sort_column == "role"
        assert state.sort_desc is False

    def test_sorting_is_applied_within_each_group(self) -> None:
        state = _state()
        state.toggle_sort("load_percent")

        assert [row.id for row in state.mine_rows] == [1]
        assert [row.id for row in state.other_rows] == [2, 3]

        state.toggle_sort("load_percent")
        assert [row.id for row in state.other_rows] == [3, 2]

    def test_filters(self) -> None:
        state = _state()
        state.set_list_filter("Überlastet")
        assert [r.id for r in [*state.mine_rows, *state.other_rows]] == [1]
        state.set_list_filter("Frei")
        assert [r.id for r in [*state.mine_rows, *state.other_rows]] == [2]
        state.set_list_filter("Meine")
        assert state.other_rows == []
        state.set_list_filter("nix")
        assert state.list_filter == "Alle"

    def test_inspector_selection(self) -> None:
        state = _state()
        assert state.inspected is not None
        assert state.inspected.id == 1
        state.inspect(3)
        assert state.inspected is not None
        assert state.inspected.id == 3
        state.toggle_inspector()
        assert state.show_inspector is False

    def test_subtitle(self) -> None:
        assert (
            _state().subtitle == "3 Mitarbeiter · 1 überlastet · 1 mit freier Kapazität"
        )


class _FakeLogin:
    def __init__(self, is_admin: bool) -> None:
        self._user = SimpleNamespace(user_id=1, is_admin=is_admin)

    @property
    async def authenticated_user(self) -> Any:
        return self._user

    async def redir(self) -> None:
        return None


def _with_login(state: TeamState, *, is_admin: bool = True) -> TeamState:
    object.__setattr__(state, "get_state", AsyncMock(return_value=_FakeLogin(is_admin)))
    return state


def test_employee_table_headers_enable_sorting() -> None:
    rendered = str(employee_list())

    for key in (
        "name",
        "role",
        "hours",
        "load_percent",
        "free_days",
        "project_count",
    ):
        assert f'"data-sort":"{key}"' in rendered
    assert "toggle_sort" in rendered
    assert "decimalScale:1" in rendered
    assert "fixedDecimalScale:true" in rendered
    assert "Summe" in rendered
    assert '"gridColumn"] : "span 4"' in rendered
    assert '["top"] : "30px"' in rendered


LOAD_INPUTS = "alloq_team.states.team_list_state.load_inputs"


def _session_ctx() -> Any:
    @asynccontextmanager
    async def _ctx() -> Any:
        yield MagicMock()

    return _ctx


class TestRefreshOverview:
    @pytest.mark.asyncio
    async def test_fills_overviews(self) -> None:
        state = _state()
        inputs = ([_alloc(2, 1, 0, 5.0)], PROJECTS, frozenset())
        with patch(LOAD_INPUTS, AsyncMock(return_value=inputs)):
            await state._refresh_overview()
        assert set(state.overviews) == {1, 2, 3}
        assert state.overviews[2].load_percent == 100

    @pytest.mark.asyncio
    async def test_error_keeps_the_last_figures(self) -> None:
        state = _state()
        before = dict(state.overviews)
        with patch(LOAD_INPUTS, AsyncMock(side_effect=RuntimeError("db down"))):
            await state._refresh_overview()
        assert state.overviews == before

    @pytest.mark.asyncio
    async def test_reloading_employees_refreshes_utilization(self) -> None:
        state = _state()
        refresh = AsyncMock()
        object.__setattr__(state, "_refresh_overview", refresh)
        with (
            patch(
                "alloq_team.states.team_state.get_asyncdb_session",
                _session_ctx(),
            ),
            patch("alloq_team.states.team_state.employee_repo") as repo,
        ):
            repo.find_all_paginated = AsyncMock(return_value=[])
            await state._load_employees()
        refresh.assert_awaited_once()


class TestLoadInputs:
    @pytest.mark.asyncio
    async def test_maps_rows(self) -> None:
        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(
                all=lambda: [(1, "Alpha", "A", "#111111"), (2, "", "B", None)]
            )
        )

        @asynccontextmanager
        async def _ctx() -> Any:
            yield session

        entity = SimpleNamespace(
            project_id=1, employee_id=5, week_start=MONDAY, person_days=2
        )
        holiday = SimpleNamespace(date=MONDAY)
        with (
            patch.object(service, "get_asyncdb_session", _ctx),
            patch.object(service, "capacity_allocation_repo") as allocations,
            patch.object(service, "public_holiday_repo") as holidays,
        ):
            allocations.find_in_range = AsyncMock(return_value=[entity])
            holidays.find_by_date_range = AsyncMock(return_value=[holiday])
            rows, projects, days = await service.load_inputs(WEEKS)
        assert rows == [Allocation(1, 5, MONDAY, 2.0)]
        assert projects[2].name == "B"
        assert projects[2].color == "#8E8E93"
        assert days == frozenset({MONDAY})


class TestRendering:
    def test_list_and_inspector(self) -> None:
        rendered = str(employee_table())
        for text in ("Meine Mitarbeiter", "Weitere Mitarbeiter", "Mitarbeiterdetails"):
            assert text in rendered
        assert "aq-thead" in str(employee_list())

    def test_toolbar(self) -> None:
        assert "aq-segmented" in str(team_filter())
        assert "Mitarbeiter anlegen" in " ".join(str(c) for c in team_toolbar())
