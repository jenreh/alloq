"""Tests for the 'Projekt planen' wizard state (distribution, capacity, save)."""

import datetime
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from alloq_commons.entities import (
    CapacityAllocationEntity,
    EmployeeEntity,
    ProjectEntity,
    RoleEntity,
)
from alloq_commons.repositories import capacity_allocation_repo
from alloq_project.states.project_plan_state import (
    ProjectPlanState,
    _distribute_with_avail,
    _weeks_between,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from appkit_user.authentication.states import LoginState

MODULE = "alloq_project.states.project_plan_state"
MON = datetime.date(2026, 1, 5)


class _FakeLogin:
    def __init__(self, *, is_admin: bool) -> None:
        self.is_admin = is_admin

    @property
    async def authenticated_user(self) -> Any:
        return SimpleNamespace(user_id=1, is_admin=self.is_admin)

    async def redir(self) -> None:
        return None


def _login(*, is_admin: bool) -> Any:
    login = _FakeLogin(is_admin=is_admin)

    async def _get_state(cls: type) -> Any:
        assert cls is LoginState
        return login

    return patch.object(
        ProjectPlanState, "get_state", AsyncMock(side_effect=_get_state)
    )


@pytest.fixture(autouse=True)
def _admin_login() -> Iterator[None]:
    with _login(is_admin=True):
        yield


async def _drain(handler: Any) -> list[Any]:
    return [event async for event in handler]


def _emp(emp_id: int, role_id: int) -> dict[str, Any]:
    return {
        "id": emp_id,
        "name": f"E{emp_id}",
        "roles": "Dev",
        "role_ids": [role_id],
        "seniority": "",
        "workload_percent": 100,
        "internal_hours": 0,
        "absences": [],
    }


def _plan_state(
    project_id: int, employees: list[dict[str, Any]], start: str, end: str
) -> ProjectPlanState:
    state = ProjectPlanState()
    state.selected_project_id = str(project_id)
    state.start_iso = start
    state.end_iso = end
    state.employee_pool = employees
    state.prior_loaded_for = state._prior_key()
    return state


@asynccontextmanager
async def _failing_session() -> AsyncIterator[Any]:
    raise RuntimeError("db down")
    yield  # pragma: no cover


class TestWeeksBetween:
    def test_counts_monday_anchored_weeks(self) -> None:
        # Wed -> Tue of the next week touches two calendar weeks.
        assert (
            _weeks_between(datetime.date(2026, 1, 7), datetime.date(2026, 1, 13)) == 2
        )

    def test_same_week(self) -> None:
        assert _weeks_between(MON, MON + datetime.timedelta(days=4)) == 1

    def test_end_before_start(self) -> None:
        assert _weeks_between(MON, MON - datetime.timedelta(days=1)) == 0


class TestRampDown:
    def test_tail_tapers_without_spike(self) -> None:
        assert _distribute_with_avail(15, 6, 0, 2, [5.0] * 6) == [
            5.0,
            5.0,
            3.33,
            1.67,
            0.0,
            0.0,
        ]

    def test_pt_is_kept_when_no_room_to_extend(self) -> None:
        result = _distribute_with_avail(20, 4, 0, 2, [5.0] * 4)
        assert sum(result) == pytest.approx(20.0)

    @pytest.mark.parametrize("total", [3, 7.5, 12, 18, 24])
    def test_conserves_pt_and_tail_is_non_increasing(self, total: float) -> None:
        result = _distribute_with_avail(total, 8, 1, 3, [5.0] * 8)
        assert sum(result) == pytest.approx(total, abs=0.03)
        used = [v for v in result[1:] if v > 0]  # after the 1 ramp-up week
        tail = used[-3:]
        assert tail == sorted(tail, reverse=True)

    def test_skips_blocked_weeks(self) -> None:
        result = _distribute_with_avail(8, 5, 0, 1, [5.0, 0.0, 5.0, 5.0, 5.0])
        assert result[1] == 0.0
        assert sum(result) == pytest.approx(8.0)


class TestCapacity:
    def test_partial_first_week_only_counts_days_in_window(self) -> None:
        # Project starts on a Friday: only one project day in week 0.
        state = _plan_state(1, [_emp(1, 3)], "2026-01-09", "2026-01-23")
        avail = state._weekly_avail(state.employee_pool[0], state._project_weeks())
        assert avail == [1.0, 5.0, 5.0]

    @pytest.mark.asyncio
    async def test_prior_load_queries_from_monday_and_loads_holidays(self) -> None:
        state = _plan_state(1, [], "2026-03-04", "2026-03-20")
        find = AsyncMock(return_value=[])
        holidays = AsyncMock(
            return_value=[SimpleNamespace(date=datetime.date(2026, 3, 6))]
        )

        @asynccontextmanager
        async def _ctx() -> AsyncIterator[Any]:
            yield AsyncMock()

        with (
            patch(f"{MODULE}.get_asyncdb_session", _ctx),
            patch(f"{MODULE}.capacity_allocation_repo.find_in_range", find),
            patch(f"{MODULE}.public_holiday_repo.find_by_date_range", holidays),
        ):
            assert await state._refresh_prior_allocations() is None
        assert find.await_args is not None
        assert find.await_args.args[1] == datetime.date(2026, 3, 2)
        assert state.holiday_dates == [datetime.date(2026, 3, 6)]

    @pytest.mark.asyncio
    async def test_prior_load_error_is_reported_not_treated_as_free(self) -> None:
        state = _plan_state(1, [], "2026-03-04", "2026-03-20")
        state.planned_pt_by_employee_week = {"1": {"2026-03-02": 5.0}}

        @asynccontextmanager
        async def _ctx() -> AsyncIterator[Any]:
            raise RuntimeError("db down")
            yield  # pragma: no cover

        with patch(f"{MODULE}.get_asyncdb_session", _ctx):
            assert await state._refresh_prior_allocations() is not None
        assert state.planned_pt_by_employee_week == {"1": {"2026-03-02": 5.0}}
        assert state.prior_ready is False

    @pytest.mark.asyncio
    async def test_failed_window_extension_blocks_next_step_and_save(self) -> None:
        state = _plan_state(1, [_emp(1, 3)], "2026-01-05", "2026-03-15")
        state.step = 1
        state.selected_employee_ids = [1]
        state.planned_by_employee = {"1": 5.0}
        apply = AsyncMock()
        with (
            patch(f"{MODULE}.get_asyncdb_session", _failing_session),
            patch(f"{MODULE}.apply_resource_plan", apply),
        ):
            assert await state.set_num_weeks("20") is not None
            assert state.next_step() is not None
            events = await _drain(state.save_plan())
        assert state.num_weeks == 20
        assert state.step == 1
        apply.assert_not_called()
        assert len(events) == 1
        assert state.is_saving is False

    @pytest.mark.asyncio
    async def test_successful_reload_makes_window_ready(self) -> None:
        state = _plan_state(1, [], "2026-01-05", "2026-03-15")

        @asynccontextmanager
        async def _ctx() -> AsyncIterator[Any]:
            yield AsyncMock()

        with (
            patch(f"{MODULE}.get_asyncdb_session", _ctx),
            patch(
                f"{MODULE}.capacity_allocation_repo.find_in_range",
                AsyncMock(return_value=[]),
            ),
            patch(
                f"{MODULE}.public_holiday_repo.find_by_date_range",
                AsyncMock(return_value=[]),
            ),
        ):
            assert await state.set_num_weeks("20") is None
        assert state.prior_ready is True

    @pytest.mark.asyncio
    async def test_set_num_weeks_keeps_ramps(self) -> None:
        state = _plan_state(1, [], "2026-01-07", "2026-03-01")
        state.ramp_up = 4
        state.ramp_down = 4
        with patch.object(ProjectPlanState, "_refresh_prior_allocations", AsyncMock()):
            await state.set_num_weeks("1")
            await state.set_num_weeks("12")
        assert (state.ramp_up, state.ramp_down) == (4, 4)
        assert state.num_weeks == 12


class TestNextStep:
    def test_needs_a_project_to_leave_step_zero(self) -> None:
        state = ProjectPlanState()
        state.next_step()
        assert state.step == 0

    @pytest.mark.asyncio
    async def test_failed_project_load_cannot_leave_step_zero(self) -> None:
        planning = SimpleNamespace(
            available_projects=[
                SimpleNamespace(
                    id=7,
                    code="P7",
                    name_de="P",
                    color=None,
                    start_date=MON,
                    end_date=datetime.date(2026, 3, 1),
                    team_initials=[],
                    required_capacities=[],
                )
            ],
            available_employees=[],
            available_roles=[],
        )
        login = _FakeLogin(is_admin=True)

        async def _get_state(cls: type) -> Any:
            return login if cls is LoginState else planning

        state = ProjectPlanState()
        with (
            patch.object(
                ProjectPlanState, "get_state", AsyncMock(side_effect=_get_state)
            ),
            patch(f"{MODULE}.get_asyncdb_session", _failing_session),
        ):
            assert await state.select_project(7) is not None
        assert state.selected_project_id == "7"
        assert state.next_step() is not None
        assert state.step == 0


async def _seed(session: AsyncSession) -> tuple[int, int, int, int]:
    project = ProjectEntity(
        code="PL",
        customer="K",
        name_de="Plan",
        start_date=MON,
        end_date=datetime.date(2026, 3, 1),
        budget=1,
    )
    alice = EmployeeEntity(first_name="Alice", last_name="A", seniority="Senior")
    bob = EmployeeEntity(first_name="Bob", last_name="B", seniority="Senior")
    role = RoleEntity(name="Dev", abbreviation="DEV")
    session.add_all([project, alice, bob, role])
    await session.flush()
    return project.id, alice.id, bob.id, role.id


def _alloc(
    pid: int, eid: int, rid: int, week: datetime.date, pd: float
) -> CapacityAllocationEntity:
    return CapacityAllocationEntity(
        project_id=pid, employee_id=eid, role_id=rid, week_start=week, person_days=pd
    )


class TestSavePlan:
    @pytest.mark.asyncio
    async def test_only_selected_employees_in_window_are_replaced(
        self, async_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        before = MON - datetime.timedelta(weeks=1)
        week2 = MON + datetime.timedelta(weeks=1)
        async with async_session_factory() as session:
            pid, alice, bob, rid = await _seed(session)
            session.add_all(
                [
                    _alloc(pid, alice, rid, before, 2.0),
                    _alloc(pid, alice, rid, week2, 5.0),
                    _alloc(pid, bob, rid, week2, 4.0),
                ]
            )
            await session.commit()

        state = _plan_state(
            pid, [_emp(alice, rid), _emp(bob, rid)], "2026-01-05", "2026-01-25"
        )
        state.selected_employee_ids = [alice]
        state.planned_by_employee = {str(alice): 6.0}

        @asynccontextmanager
        async def _ctx() -> AsyncIterator[AsyncSession]:
            async with async_session_factory() as session:
                yield session

        with patch(f"{MODULE}.get_asyncdb_session", _ctx):
            await _drain(state.save_plan())

        async with async_session_factory() as session:
            rows = await capacity_allocation_repo.find_by_project(session, pid)
        assert sorted((r.employee_id, r.week_start, r.person_days) for r in rows) == [
            (alice, before, 2.0),  # outside the window: kept
            (alice, MON, 5.0),
            (alice, week2, 1.0),
            (bob, week2, 4.0),  # not selected: kept
        ]
        assert state.is_open is False
        assert state.is_saving is False

    @pytest.mark.asyncio
    async def test_empty_plan_does_not_touch_the_database(self) -> None:
        state = _plan_state(1, [_emp(1, 3)], "2026-01-05", "2026-01-25")
        state.is_open = True
        state.selected_employee_ids = [1]
        state.planned_by_employee = {"1": 0.0}
        apply = AsyncMock()
        with patch(f"{MODULE}.apply_resource_plan", apply):
            events = await _drain(state.save_plan())
        apply.assert_not_called()
        assert len(events) == 1
        assert state.is_open is True

    @pytest.mark.asyncio
    async def test_non_admin_cannot_save(self) -> None:
        state = _plan_state(1, [_emp(1, 3)], "2026-01-05", "2026-01-25")
        state.selected_employee_ids = [1]
        state.planned_by_employee = {"1": 5.0}
        apply = AsyncMock()
        with (
            _login(is_admin=False),
            patch(f"{MODULE}.apply_resource_plan", apply),
        ):
            await _drain(state.save_plan())
        apply.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_error_resets_saving_and_keeps_modal_open(self) -> None:
        state = _plan_state(1, [_emp(1, 3)], "2026-01-05", "2026-01-25")
        state.is_open = True
        state.selected_employee_ids = [1]
        state.planned_by_employee = {"1": 5.0}

        @asynccontextmanager
        async def _ctx() -> AsyncIterator[Any]:
            yield AsyncMock()

        with (
            patch(f"{MODULE}.get_asyncdb_session", _ctx),
            patch(
                f"{MODULE}.apply_resource_plan",
                AsyncMock(side_effect=RuntimeError("boom: uq_capacities_proj")),
            ),
        ):
            events = await _drain(state.save_plan())
        assert state.is_saving is False
        assert state.is_open is True
        toast = " ".join(str(e) for e in events if e is not None)
        assert "error" in toast
        assert "uq_capacities_proj" not in toast


class TestModalRender:
    def test_save_is_gated_and_weeks_commit_on_blur(self) -> None:
        from alloq_project.components.project_plan_modal import (  # noqa: PLC0415
            project_plan_modal,
        )

        rendered = str(project_plan_modal().render())
        assert "preview_rows" in rendered
        assert "is_saving" in rendered
        assert "onBlur" in rendered
