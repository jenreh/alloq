"""Regression tests for code-review fixes in alloq-commons."""

import datetime
from contextlib import asynccontextmanager
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_commons.entities import (
    CapacityAllocationEntity,
    EmployeeEntity,
    ProjectEntity,
    RiskEntity,
    RoleEntity,
)
from alloq_commons.entities.absence import AbsenceEntity
from alloq_commons.entities.employee import SeniorityLevel
from alloq_commons.entities.public_holiday import PublicHolidayEntity
from alloq_commons.models.employee import AbsenceCreate
from alloq_commons.models.project import RiskCreate
from alloq_commons.models.public_holiday import PublicHolidayCreate
from alloq_commons.models.role import RoleCreate
from alloq_commons.repositories.employee_repository import EmployeeRepository
from alloq_commons.repositories.project_repository import ProjectRepository
from alloq_commons.repositories.public_holiday_repository import (
    PublicHolidayRepository,
)
from alloq_commons.repositories.risk_repository import RiskRepository
from alloq_commons.repositories.search import escape_like
from alloq_commons.services.quick_project import (
    QuickProjectError,
    create_quick_project,
)
from alloq_commons.services.utilization import (
    AbsencePeriod,
    UtilizationAllocationInput,
    UtilizationEmployeeInput,
    UtilizationService,
)
from alloq_commons.state.role_states import RoleState
from alloq_commons.states.holiday_state import HolidayState
from pydantic import ValidationError
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession

MONDAY = date(2026, 4, 27)


# ============================================================================
# Helpers
# ============================================================================


def _login_state(*, is_admin: bool) -> MagicMock:
    """LoginState mock whose ``authenticated_user`` is awaitable on each access."""
    user = MagicMock(is_admin=is_admin, user_id=7)

    async def _user() -> MagicMock:
        return user

    login_state = MagicMock()
    type(login_state).authenticated_user = property(lambda _self: _user())
    login_state.redir = AsyncMock(return_value=None)
    return login_state


def _with_login(state: Any, *, is_admin: bool) -> Any:
    object.__setattr__(
        state,
        "get_state",
        AsyncMock(return_value=_login_state(is_admin=is_admin)),
    )
    return state


def _session_ctx(session: Any) -> Any:
    @asynccontextmanager
    async def _ctx() -> Any:
        yield session

    return _ctx


async def _drain(gen: Any) -> list[Any]:
    return [item async for item in gen]


def _employee(first: str = "Anna", last: str = "Berg") -> EmployeeEntity:
    return EmployeeEntity(
        first_name=first,
        last_name=last,
        seniority=SeniorityLevel.SENIOR.value,
        hours_per_week=40,
    )


def _project(code: str = "PRJ") -> ProjectEntity:
    return ProjectEntity(
        code=code,
        customer="Kunde",
        name_de="Projekt",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        budget=1000,
        color="#000000",
    )


# ============================================================================
# Authorization: admin-only handlers
# ============================================================================


class TestRoleStateRequiresAdmin:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("handler", "args"),
        [
            ("create_role", ({"name": "Dev"},)),
            ("update_role", ({"name": "Dev"},)),
            ("delete_role", (1,)),
            ("load_roles", ()),
        ],
    )
    async def test_non_admin_is_rejected(self, handler: str, args: tuple) -> None:
        state = _with_login(RoleState(), is_admin=False)  # type: ignore[call-arg]
        repo = AsyncMock()
        session_factory = MagicMock()

        with (
            patch("alloq_commons.state.role_states.role_repo", repo),
            patch(
                "alloq_commons.state.role_states.get_asyncdb_session",
                session_factory,
            ),
        ):
            events = await _drain(getattr(state, handler)(*args))

        assert len(events) == 1  # the permission toast only
        session_factory.assert_not_called()
        assert repo.method_calls == []

    @pytest.mark.asyncio
    async def test_non_admin_cannot_read_role(self) -> None:
        state = _with_login(RoleState(), is_admin=False)  # type: ignore[call-arg]
        repo = AsyncMock()

        with patch("alloq_commons.state.role_states.role_repo", repo):
            await state.select_role_and_open_edit(3)

        repo.find_by_id.assert_not_called()
        assert state.edit_modal_open is False

    @pytest.mark.asyncio
    async def test_admin_passes(self) -> None:
        state = _with_login(RoleState(), is_admin=True)  # type: ignore[call-arg]
        repo = AsyncMock()
        repo.find_all_paginated = AsyncMock(return_value=[])

        with (
            patch("alloq_commons.state.role_states.role_repo", repo),
            patch(
                "alloq_commons.state.role_states.get_asyncdb_session",
                _session_ctx(AsyncMock()),
            ),
        ):
            await _drain(state.load_roles())

        repo.find_all_paginated.assert_awaited_once()


class TestHolidayStateRequiresAdmin:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("handler", "args"),
        [
            ("create_holiday", ({"name": "X", "date": "2026-01-01"},)),
            ("update_holiday", ({"name": "X", "date": "2026-01-01"},)),
            ("delete_holiday", (1,)),
            ("load_holidays", ()),
            ("change_year", ("2027",)),
        ],
    )
    async def test_non_admin_is_rejected(self, handler: str, args: tuple) -> None:
        state = _with_login(HolidayState(), is_admin=False)  # type: ignore[call-arg]
        repo = AsyncMock()
        session_factory = MagicMock()

        with (
            patch("alloq_commons.states.holiday_state.public_holiday_repo", repo),
            patch(
                "alloq_commons.states.holiday_state.get_asyncdb_session",
                session_factory,
            ),
        ):
            events = await _drain(getattr(state, handler)(*args))

        assert len(events) == 1
        session_factory.assert_not_called()
        assert repo.method_calls == []

    @pytest.mark.asyncio
    async def test_non_admin_cannot_read_holiday(self) -> None:
        state = _with_login(HolidayState(), is_admin=False)  # type: ignore[call-arg]
        repo = AsyncMock()

        with patch("alloq_commons.states.holiday_state.public_holiday_repo", repo):
            await state.select_holiday_and_open_edit(3)

        repo.find_by_id.assert_not_called()
        assert state.edit_modal_open is False


# ============================================================================
# Holiday state: year selection and session handling
# ============================================================================


class TestHolidayYear:
    def test_previous_year_is_selectable(self) -> None:
        current = datetime.datetime.now(tz=datetime.UTC).year
        years = HolidayState().available_years  # type: ignore[call-arg]
        assert years[0] == str(current - 1)
        assert str(current) in years

    @pytest.mark.asyncio
    async def test_first_load_resets_stale_default_year(self) -> None:
        state = _with_login(HolidayState(), is_admin=True)  # type: ignore[call-arg]
        state.selected_year = 1999  # stale import-time default
        repo = AsyncMock()
        repo.find_by_year = AsyncMock(return_value=[])

        with (
            patch("alloq_commons.states.holiday_state.public_holiday_repo", repo),
            patch(
                "alloq_commons.states.holiday_state.get_asyncdb_session",
                _session_ctx(AsyncMock()),
            ),
        ):
            await _drain(state.load_holidays())
            state.selected_year = 2025  # user picks a year afterwards
            await _drain(state.load_holidays())

        current = datetime.datetime.now(tz=datetime.UTC).year
        assert repo.find_by_year.await_args_list[0].args[1] == current
        assert state.selected_year == 2025  # later loads keep the user's choice


class TestToastsAfterSession:
    """Error toasts must not be yielded while the DB session is still open."""

    @staticmethod
    def _tracking_ctx() -> tuple[Any, list[bool]]:
        open_flag = [False]

        @asynccontextmanager
        async def _ctx() -> Any:
            open_flag[0] = True
            try:
                yield AsyncMock()
            finally:
                open_flag[0] = False

        return _ctx, open_flag

    @pytest.mark.asyncio
    async def test_delete_role_not_found(self) -> None:
        state = _with_login(RoleState(), is_admin=True)  # type: ignore[call-arg]
        ctx, open_flag = self._tracking_ctx()
        repo = AsyncMock()
        repo.find_by_id = AsyncMock(return_value=None)
        open_during_yield = []

        with (
            patch("alloq_commons.state.role_states.role_repo", repo),
            patch("alloq_commons.state.role_states.get_asyncdb_session", ctx),
        ):
            async for _ in state.delete_role(5):
                open_during_yield.append(open_flag[0])

        assert open_during_yield
        assert not any(open_during_yield)

    @pytest.mark.asyncio
    async def test_delete_holiday_not_found(self) -> None:
        state = _with_login(HolidayState(), is_admin=True)  # type: ignore[call-arg]
        ctx, open_flag = self._tracking_ctx()
        repo = AsyncMock()
        repo.find_by_id = AsyncMock(return_value=None)
        open_during_yield = []

        with (
            patch("alloq_commons.states.holiday_state.public_holiday_repo", repo),
            patch("alloq_commons.states.holiday_state.get_asyncdb_session", ctx),
        ):
            async for _ in state.delete_holiday(5):
                open_during_yield.append(open_flag[0])

        assert open_during_yield
        assert not any(open_during_yield)


# ============================================================================
# Utilization service
# ============================================================================


class TestUtilizationHolidaysAndWorkload:
    def test_defaults_are_unchanged(self) -> None:
        heat = UtilizationService.compute_heat_from_raw(
            used_days=3.5, internal_hours=4, absences=[], week_start=MONDAY
        )
        assert heat.available_days == pytest.approx(4.5)
        assert heat.percent == 78

    def test_holiday_reduces_capacity_like_the_grid(self) -> None:
        holiday = MONDAY + datetime.timedelta(days=4)
        heat = UtilizationService.compute_heat_from_raw(
            used_days=3.5,
            internal_hours=4,
            absences=[],
            week_start=MONDAY,
            holiday_dates={holiday},
        )
        work_days = UtilizationService.work_days_for_week(MONDAY, {holiday})
        grid = UtilizationService.compute_employee_heat(
            3.5,
            0.0,
            UtilizationService.cap_internal_days(4, 0.0, work_days),
            work_days,
        )
        assert heat == grid
        assert heat.percent == 100

    def test_part_time_workload(self) -> None:
        heat = UtilizationService.compute_heat_from_raw(
            used_days=2.0,
            internal_hours=0,
            absences=[],
            week_start=MONDAY,
            workload_percent=50,
        )
        assert heat.available_days == pytest.approx(2.5)
        assert heat.percent == 80

    def test_team_series_uses_holidays_and_workload(self) -> None:
        series = UtilizationService.compute_team_utilization_series(
            employees=[
                UtilizationEmployeeInput(
                    employee_id=1,
                    name="A",
                    role_name="Dev",
                    internal_hours=0,
                    workload_percent=50,
                )
            ],
            allocations=[
                UtilizationAllocationInput(
                    project_id=1, employee_id=1, week_start=MONDAY, person_days=2.0
                )
            ],
            week_starts=[MONDAY],
            current_week_start=MONDAY,
            free_capacity_start=MONDAY,
            holiday_dates={MONDAY},
        )
        week = series.employees[0].weeks[0]
        assert week.available_days == pytest.approx(2.0)  # (5 - 1) * 50%
        assert week.percent == 100


class TestGesamtBucketFloat:
    def test_rounding_noise_is_neutral(self) -> None:
        free = 5 - 0.5 - 4.3 - 0.2
        assert free != 0.0  # float noise that used to break the bucket
        assert UtilizationService.gesamt_bucket(free) == "neutral"
        assert UtilizationService.gesamt_bucket(-free) == "neutral"


class TestPlanningWeekStarts:
    def test_default_anchor_rolls_with_today(self) -> None:
        weeks = UtilizationService.planning_week_starts(3)
        monday = UtilizationService.monday_of(date.today())  # noqa: DTZ011
        assert weeks[0] == monday
        assert weeks[2] == monday + datetime.timedelta(weeks=2)

    def test_explicit_anchor(self) -> None:
        assert UtilizationService.planning_week_starts(1, MONDAY) == [MONDAY]

    def test_absence_period_still_counts(self) -> None:
        heat = UtilizationService.compute_heat_from_raw(
            used_days=0.0,
            internal_hours=0,
            absences=(AbsencePeriod(MONDAY, MONDAY + datetime.timedelta(days=4)),),
            week_start=MONDAY,
        )
        assert heat.is_absent is True


# ============================================================================
# Entities and models
# ============================================================================


class TestEmployeeAbsencesSince:
    @staticmethod
    def _entity() -> EmployeeEntity:
        employee = _employee()
        employee.id = 1
        employee.absences = [
            AbsenceEntity(start_date=date(2026, 9, 21), end_date=date(2026, 9, 23)),
            AbsenceEntity(start_date=date(2026, 1, 5), end_date=date(2026, 1, 9)),
        ]
        return employee

    def test_absence_before_since_is_dropped(self) -> None:
        assert (
            self._entity().to_dict(absences_since=date(2026, 9, 24))["absences"] == []
        )

    def test_since_keeps_absences_in_displayed_range(self) -> None:
        absences = self._entity().to_dict(absences_since=date(2026, 9, 14))["absences"]
        assert [a["start_date"] for a in absences] == [date(2026, 9, 21)]


class TestProjectTeamSkipsZeroAllocations:
    def test_zero_day_rows_are_not_team_members(self) -> None:
        busy, cleared = _employee("Anna", "Berg"), _employee("Carl", "Dorn")
        busy.id, cleared.id = 1, 2
        project = _project()
        project.capacity_allocations = [
            CapacityAllocationEntity(employee=busy, week_start=MONDAY, person_days=1.0),
            CapacityAllocationEntity(
                employee=cleared, week_start=MONDAY, person_days=0.0
            ),
        ]
        assert project._team_initials() == ["AB"]
        assert project._team_members() == [{"initials": "AB", "name": "Anna Berg"}]


class TestModelValidation:
    def test_blank_role_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RoleCreate(name="")

    def test_blank_holiday_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PublicHolidayCreate(name="", date=MONDAY)

    def test_reversed_absence_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AbsenceCreate(
                employee_id=1, start_date=date(2026, 10, 10), end_date=date(2026, 10, 1)
            )

    def test_single_day_absence_allowed(self) -> None:
        assert AbsenceCreate(employee_id=1, start_date=MONDAY, end_date=MONDAY)

    @pytest.mark.parametrize("impact", [0, 6])
    def test_risk_impact_bounds(self, impact: int) -> None:
        with pytest.raises(ValidationError):
            RiskCreate(project_id=1, name="R", impact=impact)


class TestConstraintsDeclared:
    @pytest.mark.parametrize(
        ("entity", "name"),
        [
            (CapacityAllocationEntity, "ck_capacity_allocations_person_days"),
            (ProjectEntity, "ck_projects_date_range"),
        ],
    )
    def test_check_constraint_matches_migration(self, entity: Any, name: str) -> None:
        names = {c.name for c in entity.__table__.constraints}
        assert name in names

    @pytest.mark.asyncio
    async def test_negative_person_days_rejected(
        self, async_session: AsyncSession
    ) -> None:
        employee, project, role = _employee(), _project(), RoleEntity(name="Dev")
        async_session.add_all([employee, project, role])
        await async_session.flush()
        async_session.add(
            CapacityAllocationEntity(
                project_id=project.id,
                employee_id=employee.id,
                role_id=role.id,
                week_start=MONDAY,
                person_days=-1.0,
            )
        )
        with pytest.raises(Exception, match="CHECK constraint"):
            await async_session.flush()


class TestLazyProjectRelationship:
    @pytest.mark.asyncio
    async def test_allocation_project_is_not_loaded_implicitly(
        self, async_session: AsyncSession
    ) -> None:
        employee, project, role = _employee(), _project(), RoleEntity(name="Dev")
        async_session.add_all([employee, project, role])
        await async_session.flush()
        async_session.add(
            CapacityAllocationEntity(
                project_id=project.id,
                employee_id=employee.id,
                role_id=role.id,
                week_start=MONDAY,
                person_days=1.0,
            )
        )
        await async_session.flush()
        async_session.expunge_all()

        from sqlalchemy import select  # noqa: PLC0415

        result = await async_session.execute(select(CapacityAllocationEntity))
        allocation = result.scalars().one()
        with pytest.raises(InvalidRequestError):
            _ = allocation.project


# ============================================================================
# Repositories and services
# ============================================================================


class TestRecurringHolidays:
    @pytest.mark.asyncio
    async def test_recurring_holiday_projects_to_later_year(
        self, async_session: AsyncSession
    ) -> None:
        async_session.add_all(
            [
                PublicHolidayEntity(
                    name="Tag der Arbeit", date=date(2026, 5, 1), is_recurring=True
                ),
                PublicHolidayEntity(
                    name="Ostermontag", date=date(2026, 4, 6), is_recurring=False
                ),
            ]
        )
        await async_session.flush()

        rows = await PublicHolidayRepository().find_by_date_range(
            async_session, date(2027, 1, 1), date(2027, 12, 31)
        )

        assert [(r.name, r.date) for r in rows] == [
            ("Tag der Arbeit", date(2027, 5, 1))
        ]
        assert rows[0] not in async_session

    @pytest.mark.asyncio
    async def test_stored_row_is_not_duplicated(
        self, async_session: AsyncSession
    ) -> None:
        async_session.add_all(
            [
                PublicHolidayEntity(
                    name="Neujahr", date=date(2026, 1, 1), is_recurring=True
                ),
                PublicHolidayEntity(
                    name="Neujahr", date=date(2027, 1, 1), is_recurring=True
                ),
            ]
        )
        await async_session.flush()

        rows = await PublicHolidayRepository().find_by_date_range(
            async_session, date(2026, 12, 1), date(2027, 1, 31)
        )

        assert [r.date for r in rows] == [date(2027, 1, 1)]


class TestLikeEscaping:
    def test_escape_like(self) -> None:
        assert escape_like("a_b%c\\") == "a\\_b\\%c\\\\"

    @pytest.mark.asyncio
    async def test_underscore_matches_literally(
        self, async_session: AsyncSession
    ) -> None:
        async_session.add_all([_employee("a_b", "X"), _employee("aXb", "Y")])
        async_session.add_all([_project("A_B"), _project("AXB")])
        await async_session.flush()

        employees = await EmployeeRepository().find_all_paginated(
            async_session, search="a_b"
        )
        projects = await ProjectRepository().find_all_paginated(
            async_session, search="a_b"
        )
        everything = await ProjectRepository().find_all_paginated(
            async_session, search="%"
        )

        assert [e.first_name for e in employees] == ["a_b"]
        assert [p.code for p in projects] == ["A_B"]
        assert everything == []


class TestRiskScoreClamp:
    @pytest.mark.asyncio
    async def test_sql_score_matches_read_model(
        self, async_session: AsyncSession
    ) -> None:
        project = _project()
        async_session.add(project)
        await async_session.flush()
        async_session.add_all(
            [
                RiskEntity(project_id=project.id, name="big", probability=3, impact=7),
                RiskEntity(project_id=project.id, name="ok", probability=4, impact=4),
            ]
        )
        await async_session.flush()

        rows = await RiskRepository().find_open_by_min_score(
            async_session, min_score=16
        )

        # impact 7 clamps to 5 -> 15 < 16, exactly as the Risk read model shows
        assert [r.name for r in rows] == ["ok"]


class TestQuickProjectRace:
    @pytest.mark.asyncio
    async def test_integrity_error_maps_to_domain_error(
        self, async_session: AsyncSession
    ) -> None:
        await create_quick_project(async_session, "Erstes", "NEU")

        with (
            patch(
                "alloq_commons.services.quick_project.project_repo.find_by_code",
                AsyncMock(return_value=None),
            ),
            pytest.raises(QuickProjectError, match="bereits vergeben"),
        ):
            await create_quick_project(async_session, "Zweites", "NEU")


class TestStatesPackage:
    def test_commons_states_do_not_export_team_state(self) -> None:
        from alloq_commons import states  # noqa: PLC0415

        assert "TeamState" not in states.__all__
        assert not hasattr(states, "TeamState")
