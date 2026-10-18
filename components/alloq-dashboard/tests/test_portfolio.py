"""Tests for the portfolio overview: scope, resource-critical path, assembly."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest
from alloq_commons.entities.project import ProjectStateEnum
from alloq_dashboard.services import portfolio
from alloq_dashboard.services.portfolio_inputs import (
    SCOPE_DEPARTMENT,
    SCOPE_TEAM,
    AllocationInput,
    EmployeeInput,
    PortfolioInputs,
    ProjectInput,
    RiskInput,
    RoleInput,
    apply_scope,
)
from alloq_dashboard.services.resource_path import (
    Calendar,
    Capacity,
    analyse_projects,
    buffer_label,
    buffer_tone,
    format_days,
    person_details,
    role_demands,
    role_details,
    weakest,
)

TODAY = date(2026, 10, 18)  # Sunday, KW 42
MONDAY = date(2026, 10, 12)
BACKEND = 1
QA = 2
ROLES = (RoleInput(BACKEND, "Backend"), RoleInput(QA, "QA"))


def week(i: int) -> date:
    return MONDAY + timedelta(weeks=i)


def friday(i: int) -> date:
    return week(i) + timedelta(days=4)


def emp(
    emp_id: int,
    name: str,
    roles: tuple[int, ...] = (BACKEND,),
    manager_id: int | None = None,
    absences: tuple[tuple[date, date], ...] = (),
) -> EmployeeInput:
    return EmployeeInput(
        id=emp_id,
        name=name,
        role_ids=roles,
        manager_id=manager_id,
        internal_hours=0,
        absences=absences,
    )


def alloc(emp_id: int, i: int, days: float, role: int = BACKEND) -> AllocationInput:
    return AllocationInput(
        employee_id=emp_id, role_id=role, week_start=week(i), person_days=days
    )


def project(
    pid: int,
    code: str,
    *,
    end: date,
    start: date = date(2026, 6, 1),
    state: str = ProjectStateEnum.ACTIVE.value,
    required: tuple[tuple[int, float], ...] = (),
    allocations: tuple[AllocationInput, ...] = (),
    owners: tuple[int, ...] = (),
    budget: int = 100_000,
    eac: float = 0.0,
    progress: int = 50,
) -> ProjectInput:
    return ProjectInput(
        id=pid,
        code=code,
        name=f"Projekt {code}",
        state=state,
        start_date=start,
        end_date=end,
        budget=budget,
        progress=progress,
        eac=eac,
        owner_ids=owners,
        required=required,
        allocations=allocations,
    )


def inputs(
    projects: tuple[ProjectInput, ...],
    employees: tuple[EmployeeInput, ...],
    *,
    risks: tuple[RiskInput, ...] = (),
    current: int | None = None,
) -> PortfolioInputs:
    return PortfolioInputs(
        projects=projects,
        all_projects=projects,
        employees=employees,
        all_employees=employees,
        roles=ROLES,
        risks=risks,
        current_employee_id=current,
    )


def lines_for(data: PortfolioInputs) -> dict[int, list]:
    capacity = Capacity(data, Calendar.for_today(TODAY))
    return analyse_projects(data, capacity)


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------


def test_format_helpers() -> None:
    assert format_days(34.0) == "34"
    assert format_days(12.46) == "12,5"
    assert buffer_label(-3) == "\u22123"
    assert buffer_label(2) == "+2"
    assert buffer_tone(-1) == "neg"
    assert buffer_tone(1) == "warn"
    assert buffer_tone(4) == ""


def test_calendar_index_counts_weeks_from_this_monday() -> None:
    cal = Calendar.for_today(TODAY)
    assert cal.monday == MONDAY
    assert cal.index(date(2026, 10, 25)) == 1
    assert cal.index(date(2026, 10, 9)) == -1
    assert cal.week(2) == date(2026, 10, 26)


# --------------------------------------------------------------------------
# Scope
# --------------------------------------------------------------------------


def test_team_scope_keeps_direct_reports_and_owned_projects() -> None:
    boss, report, other = emp(1, "Chefin"), emp(2, "A", manager_id=1), emp(3, "B")
    owned = project(10, "P10", end=friday(4), owners=(1,))
    foreign = project(11, "P11", end=friday(4), owners=(3,))
    data = inputs((owned, foreign), (boss, report, other), current=1)

    scoped = apply_scope(data, SCOPE_TEAM)

    assert [e.id for e in scoped.employees] == [2]
    assert [p.id for p in scoped.projects] == [10]
    assert apply_scope(data, SCOPE_DEPARTMENT) is data


def test_team_scope_without_profile_is_empty() -> None:
    data = inputs((project(10, "P10", end=friday(4), owners=(1,)),), (emp(1, "A"),))
    scoped = apply_scope(data, SCOPE_TEAM)
    assert scoped.employees == ()
    assert scoped.projects == ()


# --------------------------------------------------------------------------
# Capacity
# --------------------------------------------------------------------------


def test_free_capacity_is_not_clamped_when_overbooked() -> None:
    p = project(1, "P1", end=friday(4), allocations=(alloc(1, 0, 7),))
    capacity = Capacity(inputs((p,), (emp(1, "A"),)), Calendar.for_today(TODAY))

    assert capacity.free(BACKEND, 0) == pytest.approx(-2.0)
    assert capacity.free(BACKEND, 1) == pytest.approx(5.0)
    assert capacity.percent(1) == 140
    assert capacity.percent(99) is None


def test_bookings_in_other_roles_reduce_role_availability() -> None:
    p = project(1, "P1", end=friday(4), allocations=(alloc(1, 0, 3, role=QA),))
    capacity = Capacity(
        inputs((p,), (emp(1, "A", roles=(BACKEND, QA)),)), Calendar.for_today(TODAY)
    )
    assert capacity.role_available[BACKEND][0] == pytest.approx(2.0)
    assert capacity.free(QA, 0) == pytest.approx(2.0)


def test_completed_projects_do_not_book_capacity() -> None:
    done = project(
        1,
        "P1",
        end=friday(4),
        state=ProjectStateEnum.COMPLETED.value,
        allocations=(alloc(1, 0, 5),),
    )
    capacity = Capacity(inputs((done,), (emp(1, "A"),)), Calendar.for_today(TODAY))
    assert capacity.free(BACKEND, 0) == pytest.approx(5.0)


# --------------------------------------------------------------------------
# Buffer and weakest link
# --------------------------------------------------------------------------


def test_planned_work_sets_the_cover_week() -> None:
    # Required 12, 2 already booked last week, the remaining 10 planned.
    p = project(
        1,
        "P1",
        end=friday(5),
        required=((BACKEND, 12),),
        allocations=(alloc(1, -1, 2), alloc(1, 0, 5), alloc(1, 1, 5)),
    )
    line = lines_for(inputs((p,), (emp(1, "Anna"), emp(2, "Ben"))))[1][0]

    assert line.remaining_days == 10
    assert line.planned_days == 10
    assert line.gap_days == 0
    assert line.buffer_weeks == 4
    assert line.tone == "warn"
    assert line.reason == "Einzige Person für die Rolle."
    assert line.person_label == "Anna"


def test_gap_without_carrier_gives_negative_buffer() -> None:
    # 30 PT gap, one free person with 5 PT a week: covered in week 5, ends week 2.
    p = project(1, "P1", end=friday(2), required=((BACKEND, 30),))
    line = lines_for(inputs((p,), (emp(1, "A"),)))[1][0]

    assert line.gap_days == 30
    assert line.buffer_weeks == -3
    assert line.person_label == "niemand eingeplant"
    assert line.tone == "neg"
    assert line.reason == "30 PT ohne Plan."


def test_uncovered_gap_is_flagged() -> None:
    p = project(1, "P1", end=friday(2), required=((QA, 10),))
    line = lines_for(inputs((p,), (emp(1, "A"),)))[1][0]

    assert line.covered is False
    assert line.tone == "neg"
    assert line.reason.startswith("Nicht gedeckt in 52 Wochen.")


def test_overbooked_role_is_named_with_its_first_week() -> None:
    p = project(
        1,
        "P1",
        end=friday(6),
        required=((BACKEND, 20),),
        allocations=(alloc(1, 2, 7),),
    )
    line = lines_for(inputs((p,), (emp(1, "A"),)))[1][0]

    assert line.tone == "neg"
    assert line.reason == "Rolle ab KW 44 überbucht. 13 PT ohne Plan."


def test_single_absent_carrier_is_a_warning() -> None:
    carrier = emp(1, "Mira", absences=((week(2), friday(3)),))
    p = project(
        1,
        "P1",
        end=friday(8),
        required=((BACKEND, 4),),
        allocations=(alloc(1, 0, 4),),
    )
    line = lines_for(inputs((p,), (carrier, emp(2, "B"))))[1][0]

    assert line.tone == "warn"
    assert line.reason == "Einzige Person für die Rolle. Abwesend KW 44 bis KW 45."


def test_overloaded_carrier_near_the_end() -> None:
    p = project(
        1,
        "P1",
        end=friday(3),
        required=((BACKEND, 6),),
        allocations=(alloc(1, 0, 6),),
    )
    line = lines_for(inputs((p,), (emp(1, "Jonas"), emp(2, "B"))))[1][0]

    assert line.tone == "neg"
    assert line.person_label == "Jonas"
    assert line.reason == "120 % ausgelastet. Das Projekt endet am 06.11."


def test_several_carriers_with_gap_and_covered() -> None:
    staffed = project(
        1,
        "P1",
        end=friday(10),
        required=((BACKEND, 6),),
        allocations=(alloc(1, 0, 3), alloc(2, 0, 2), alloc(3, 0, 1)),
    )
    gap = project(
        2,
        "P2",
        end=friday(10),
        required=((BACKEND, 8),),
        allocations=(alloc(1, 1, 2), alloc(2, 1, 2)),
    )
    team = (emp(1, "A"), emp(2, "B"), emp(3, "C"))
    lines = lines_for(inputs((staffed, gap), team))

    assert lines[1][0].person_label == "A, B +1"
    assert lines[1][0].reason == "Bedarf gedeckt bis KW 42."
    assert lines[2][0].reason == "4 PT ohne Plan."


def test_earlier_project_gets_free_capacity_first() -> None:
    late = project(1, "LATE", end=friday(8), required=((BACKEND, 10),))
    early = project(2, "EARLY", end=friday(3), required=((BACKEND, 10),))
    lines = lines_for(inputs((late, early), (emp(1, "A"),)))

    assert lines[2][0].buffer_weeks == 2  # covered in week 1
    assert lines[1][0].buffer_weeks == 5  # covered in week 3


def test_weakest_prefers_smaller_buffer_then_severity() -> None:
    p = project(
        1,
        "P1",
        end=friday(6),
        required=((BACKEND, 5), (QA, 5)),
        allocations=(alloc(1, 0, 5), alloc(2, 0, 5, role=QA)),
    )
    team = (emp(1, "A"), emp(2, "Q", roles=(QA,)), emp(3, "Q2", roles=(QA,)))
    lines = lines_for(inputs((p,), team))[1]

    assert weakest([]) is None
    first = weakest(lines)
    assert first is not None
    assert first.role_name in {"Backend", "QA"}
    worse = lines[1].model_copy(update={"buffer_weeks": -1})
    assert weakest([lines[0], worse]) is worse


def test_fulfilled_role_cannot_delay_an_overdue_project() -> None:
    p = project(
        1,
        "P1",
        end=date(2026, 9, 25),
        required=((BACKEND, 4),),
        allocations=(alloc(1, -6, 4),),
    )
    line = lines_for(inputs((p,), (emp(1, "A"),)))[1][0]

    assert line.remaining_days == 0
    assert line.buffer_weeks == 0
    assert line.tone == ""
    assert line.reason == "Bedarf erfüllt."


def test_projects_without_required_capacity_have_no_lines() -> None:
    p = project(1, "P1", end=friday(4))
    assert lines_for(inputs((p,), (emp(1, "A"),)))[1] == []


# --------------------------------------------------------------------------
# Role demand
# --------------------------------------------------------------------------


def test_role_demand_adds_gap_share_inside_horizon() -> None:
    # 26 weeks left, 13 of them in the horizon: half of the 20 PT gap counts.
    p = project(
        1,
        "P1",
        end=friday(25),
        required=((BACKEND, 30),),
        allocations=(alloc(1, 0, 10),),
    )
    data = inputs((p,), (emp(1, "A"),))
    capacity = Capacity(data, Calendar.for_today(TODAY))
    rows = role_demands(data, capacity, analyse_projects(data, capacity))

    assert [r.role_name for r in rows] == ["Backend"]
    backend = rows[0]
    assert backend.available_days == 65
    assert backend.planned_days == 10
    assert backend.need_days == 20
    assert backend.gap_days == 10
    assert backend.plan_width == "12.3%"
    assert backend.overbooked is False


def test_role_demand_marks_overbooking_and_skips_empty_roles() -> None:
    p = project(1, "P1", end=friday(4), allocations=(alloc(1, 0, 70),))
    data = inputs((p,), (emp(1, "A"),))
    capacity = Capacity(data, Calendar.for_today(TODAY))
    rows = role_demands(data, capacity, analyse_projects(data, capacity))

    assert len(rows) == 1
    assert rows[0].overbooked is True
    assert rows[0].plan_width == "80.0%"
    assert rows[0].over_width == "6.2%"


# --------------------------------------------------------------------------
# Portfolio assembly
# --------------------------------------------------------------------------


def test_health_and_elapsed() -> None:
    assert portfolio.health(0, 100) == ""
    assert portfolio.health(90, 100) == "green"
    assert portfolio.health(105, 100) == "yellow"
    assert portfolio.health(120, 100) == "red"
    p = project(1, "P1", start=date(2026, 10, 1), end=date(2026, 11, 4))
    assert portfolio.elapsed_percent(p, TODAY) == 50
    same_day = project(2, "P2", start=TODAY, end=TODAY)
    assert portfolio.elapsed_percent(same_day, TODAY) == 100


def test_risk_bands_and_severity() -> None:
    assert [portfolio.risk_band(s) for s in (4, 9, 15, 19, 20)] == [
        "r1",
        "r2",
        "r3",
        "r4",
        "r5",
    ]
    assert portfolio.severity(4) == "low"
    assert portfolio.severity(15) == "medium"
    assert portfolio.severity(16) == "high"


def _sample() -> PortfolioInputs:
    team = (
        emp(1, "Katrin", roles=()),
        emp(2, "Jonas", manager_id=1),
        emp(3, "Lena", roles=(QA,), manager_id=1),
    )
    late = project(
        1,
        "AQ-104",
        end=friday(2),
        required=((BACKEND, 30),),
        owners=(1,),
        budget=720_000,
        eac=810_000,
        state=ProjectStateEnum.AT_RISK.value,
        progress=41,
    )
    calm = project(
        2,
        "AQ-112",
        end=friday(30),
        required=((QA, 5),),
        allocations=(alloc(3, 0, 5, role=QA),),
        budget=390_000,
        eac=385_000,
    )
    planned = project(3, "AQ-118", end=friday(20), state=ProjectStateEnum.PLANNED.value)
    done = project(4, "AQ-098", end=date(2026, 9, 25), state="Abgeschlossen")
    risks = (
        RiskInput(1, 1, "Schnittstelle", 4, 5),
        RiskInput(2, 1, "Team überbucht", 5, 4),
        RiskInput(3, 2, "Datenschutz", 2, 4),
        RiskInput(4, 2, "Akzeptanz", 1, 2),
        RiskInput(5, 2, "Erledigt", 3, 3, mitigation_status="resolved"),
    )
    return inputs((late, calm, planned, done), team, risks=risks, current=1)


def test_build_portfolio_for_the_department() -> None:
    kpi = portfolio.build_portfolio(_sample(), SCOPE_DEPARTMENT, TODAY)

    assert kpi.scope == "department"
    assert kpi.notice == ""
    assert kpi.department_employee_count == 3
    assert kpi.team_employee_count == 2
    assert [p.code for p in kpi.projects] == ["AQ-104", "AQ-112", "AQ-118"]
    late = kpi.projects[0]
    assert late.health == "red"
    assert late.eac_delta_percent == 12.5
    assert late.buffer_label == "\u22123"
    assert late.weakest.role_name == "Backend"

    assert [b.code for b in kpi.bubbles] == ["AQ-104", "AQ-112"]
    assert kpi.bubbles[0].negative_buffer is True
    assert kpi.bubbles[0].size == "60px"
    assert kpi.bubbles[0].top == "calc(59% - 30.0px)"
    assert kpi.bubbles[0].label_top == "calc(59% - 8px)"
    assert "Budget 720.000 €" in kpi.bubbles[0].tooltip
    assert kpi.not_plotted_label == (
        "Nicht im Diagramm: 1 geplantes Projekt (AQ-118) und 1 abgeschlossenes."
    )

    assert kpi.risk_open_total == 4
    assert (kpi.risk_high, kpi.risk_medium, kpi.risk_low) == (2, 1, 1)
    assert kpi.risks[0].score == 20
    cells = {c.key: c.count for row in kpi.matrix for c in row.cells}
    assert cells["4-5"] == 1
    assert cells["3-3"] == 0
    assert kpi.matrix[0].probability == 5

    assert [p.code for p in kpi.chains] == ["AQ-104"]
    assert kpi.comfortable_label == (
        "Mit 4 Wochen Puffer oder mehr: AQ-112 +30. Ohne erfassten Bedarf: 1 Projekt."
    )
    assert kpi.gap_total == pytest.approx(30.0)


def test_build_portfolio_for_direct_reports() -> None:
    kpi = portfolio.build_portfolio(_sample(), SCOPE_TEAM, TODAY)
    assert kpi.scope == "team"
    assert [p.code for p in kpi.projects] == ["AQ-104"]
    assert kpi.risk_open_total == 2


def test_build_portfolio_notices_and_unknown_scope() -> None:
    no_profile = replace(_sample(), current_employee_id=None)
    assert portfolio.build_portfolio(no_profile, SCOPE_TEAM, TODAY).notice == (
        portfolio.NO_PROFILE_NOTICE
    )
    lonely = replace(_sample(), current_employee_id=3)
    assert portfolio.build_portfolio(lonely, SCOPE_TEAM, TODAY).notice == (
        portfolio.EMPTY_TEAM_NOTICE
    )
    assert portfolio.build_portfolio(_sample(), "x", TODAY).scope == "department"


def test_bubble_label_flips_near_the_right_edge() -> None:
    p = portfolio.PortfolioProject(
        id=1, code="X", state="Aktiv", elapsed_percent=95, budget=100, progress=10
    )
    bubble = portfolio.bubbles([p])[0]
    assert bubble.label_left.startswith("calc(95% - ")
    assert portfolio.not_plotted_label([]) == ""


# --------------------------------------------------------------------------
# Role and person details
# --------------------------------------------------------------------------


def test_role_line_names_the_person_to_open() -> None:
    overloaded = project(
        1, "P1", end=friday(3), required=((BACKEND, 6),), allocations=(alloc(2, 0, 6),)
    )
    unstaffed = project(2, "P2", end=friday(2), required=((QA, 10),))
    lines = lines_for(inputs((overloaded, unstaffed), (emp(1, "A"), emp(2, "Jonas"))))

    assert lines[1][0].person_id == 2
    assert lines[2][0].person_id == 0


def _details_sample() -> tuple[PortfolioInputs, Capacity, dict[int, list]]:
    late = project(
        1,
        "P1",
        end=friday(4),
        required=((BACKEND, 20),),
        allocations=(alloc(1, 0, 7), alloc(1, -1, 2), alloc(1, 20, 4)),
    )
    calm = project(
        2,
        "P2",
        end=friday(10),
        required=((QA, 2),),
        allocations=(alloc(2, 1, 2, role=QA),),
    )
    done = project(
        3,
        "P3",
        end=friday(4),
        state=ProjectStateEnum.COMPLETED.value,
        allocations=(alloc(2, 0, 1),),
    )
    team = (
        emp(1, "Anna"),
        emp(
            2,
            "Mira",
            roles=(BACKEND, QA),
            absences=(
                (date(2026, 9, 1), date(2026, 9, 5)),
                (date(2026, 10, 8), date(2026, 10, 13)),
                (week(2), friday(3)),
            ),
        ),
    )
    data = inputs((late, calm, done), team)
    capacity = Capacity(data, Calendar.for_today(TODAY))
    return data, capacity, analyse_projects(data, capacity)


def test_role_detail_shows_weeks_people_and_gaps() -> None:
    data, capacity, lines = _details_sample()
    details = {d.role_name: d for d in role_details(data, capacity, lines)}

    backend = details["Backend"]
    assert backend.role_id == BACKEND
    assert len(backend.weeks) == 13
    first = backend.weeks[0]
    assert first.label == "KW 42"
    assert first.available_days == pytest.approx(8.0)
    assert first.planned_days == pytest.approx(7.0)
    assert first.free_days == pytest.approx(1.0)
    assert first.tone == ""
    assert backend.weeks[2].free_days == pytest.approx(5.0)
    assert [p.name for p in backend.people] == ["Anna", "Mira"]
    assert backend.people[0].employee_id == 1
    assert backend.people[0].planned_days == pytest.approx(7.0)
    assert [g.code for g in backend.gap_projects] == ["P1"]
    assert backend.gap_projects[0].gap_days == pytest.approx(7.0)
    assert backend.gap_projects[0].buffer_label != ""
    assert backend.employee_count == 2

    qa = details["QA"]
    assert qa.gap_projects == []
    assert qa.planned_days == pytest.approx(2.0)


def test_role_detail_free_days_go_negative_when_overbooked() -> None:
    p = project(1, "P1", end=friday(4), allocations=(alloc(1, 0, 7),))
    data = inputs((p,), (emp(1, "A"),))
    capacity = Capacity(data, Calendar.for_today(TODAY))
    backend = role_details(data, capacity, analyse_projects(data, capacity))[0]

    assert backend.weeks[0].free_days == pytest.approx(-2.0)
    assert backend.weeks[0].tone == "neg"
    assert backend.free_days == pytest.approx(58.0)
    assert backend.people[0].avg_percent == 11


def test_person_detail_shows_weeks_absences_and_bookings() -> None:
    data, capacity, lines = _details_sample()
    people = {p.employee_id: p for p in person_details(data, capacity, lines)}

    mira = people[2]
    assert mira.name == "Mira"
    assert mira.roles_label == "Backend, QA"
    assert len(mira.weeks) == 13
    assert mira.weeks[0].label == "KW 42"
    assert mira.weeks[0].available_days == pytest.approx(3.0)
    assert mira.weeks[1].booked_days == pytest.approx(2.0)
    assert mira.weeks[1].percent == 40
    assert mira.weeks[2].absent is True
    assert [a.label for a in mira.absences] == [
        "12.10. bis 13.10.2026",
        "26.10. bis 06.11.2026",
    ]
    assert [a.days for a in mira.absences] == [2, 10]
    assert mira.absent_days == 12

    anna = people[1]
    assert anna.weeks[0].percent == 140
    assert anna.weeks[0].tone == "neg"
    assert anna.weeks[0].bar_width == "100%"
    assert anna.absences == []
    assert [(b.code, b.role_name, b.days) for b in anna.bookings] == [
        ("P1", "Backend", 7.0)
    ]
    assert anna.bookings[0].in_scope is True
    assert [(b.code, b.role_id) for b in mira.bookings] == [("P2", QA)]


def test_person_details_cover_scope_and_named_carriers() -> None:
    outsider = emp(9, "Extern")
    p = project(
        1, "P1", end=friday(3), required=((BACKEND, 6),), allocations=(alloc(9, 0, 6),)
    )
    full = inputs((p,), (emp(1, "A"), outsider))
    scoped = replace(full, employees=(emp(1, "A"),))
    capacity = Capacity(scoped, Calendar.for_today(TODAY))
    lines = analyse_projects(scoped, capacity)

    ids = [d.employee_id for d in person_details(scoped, capacity, lines)]
    assert ids == [1, 9]


def test_build_portfolio_carries_role_and_person_details() -> None:
    kpi = portfolio.build_portfolio(_sample(), SCOPE_TEAM, TODAY)

    assert [r.role_name for r in kpi.role_details] == ["Backend", "QA"]
    assert [p.name for p in kpi.person_details] == ["Jonas", "Lena"]
