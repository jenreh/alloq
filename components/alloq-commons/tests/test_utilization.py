"""Tests for shared utilization calculations."""

from datetime import date

from alloq_commons.services.utilization import (
    AbsencePeriod,
    UtilizationAllocationInput,
    UtilizationEmployeeInput,
    UtilizationService,
)


def test_team_utilization_matches_heatmap_cell_deduplication() -> None:
    """Duplicate role rows collapse to one heatmap project cell."""
    week_start = date(2026, 4, 27)
    employees = [
        UtilizationEmployeeInput(
            employee_id=1,
            name="Ada Lovelace",
            role_name="Engineer",
            internal_hours=0,
            absences=(),
        ),
        UtilizationEmployeeInput(
            employee_id=2,
            name="Grace Hopper",
            role_name="Architect",
            internal_hours=0,
            absences=(),
        ),
    ]
    allocations = [
        UtilizationAllocationInput(
            project_id=10,
            employee_id=1,
            week_start=week_start,
            person_days=1.0,
        ),
        UtilizationAllocationInput(
            project_id=10,
            employee_id=1,
            week_start=week_start,
            person_days=2.0,
        ),
        UtilizationAllocationInput(
            project_id=20,
            employee_id=1,
            week_start=week_start,
            person_days=1.0,
        ),
    ]

    result = UtilizationService.compute_team_utilization_series(
        employees=employees,
        allocations=allocations,
        week_starts=[week_start],
        current_week_start=week_start,
        free_capacity_start=week_start,
    )

    assert result.employees[0].weeks[0].used_days == 3.0
    assert result.employees[0].weeks[0].percent == 60
    assert result.employees[1].weeks[0].percent == 0
    assert result.weeks[0].percent == 30


def test_heat_from_raw_caps_internal_hours_after_absence() -> None:
    """Internal days follow the same cap as the heatmap."""
    week_start = date(2026, 4, 27)
    result = UtilizationService.compute_heat_from_raw(
        used_days=1.0,
        internal_hours=32,
        absences=(
            AbsencePeriod(
                start_date=date(2026, 4, 27),
                end_date=date(2026, 4, 29),
            ),
        ),
        week_start=week_start,
    )

    assert result.available_days == 0.0
    assert result.percent == 0
