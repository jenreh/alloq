"""Tests for the project list sorting helper."""

from datetime import date

import pytest
from alloq_commons.models.project import Project
from alloq_project.services.project_sorting import (
    DEFAULT_SORT_COLUMN,
    SORT_COLUMNS,
    sort_projects,
)


def _codes(projects: list[Project]) -> list[str]:
    return [p.code for p in projects]


@pytest.fixture
def projects() -> list[Project]:
    return [
        Project(
            code="B",
            name_de="beta",
            customer="Zeta AG",
            state="Risiko",
            start_date=date(2026, 3, 1),
            budget=200,
            current_spent=50,
            current_progress=10,
            risk_count=2,
        ),
        Project(
            code="A",
            name_de="Alpha",
            customer="acme",
            state="Abgeschlossen",
            start_date=None,
            budget=300,
            current_spent=90,
            current_progress=100,
            risk_count=0,
        ),
        Project(
            code="C",
            name_de="Gamma",
            customer="Muster",
            state="Geplant",
            start_date=date(2026, 1, 1),
            budget=100,
            current_spent=10,
            current_progress=40,
            risk_count=1,
        ),
    ]


class TestSortProjects:
    """Tests for sort_projects."""

    def test_empty_list(self) -> None:
        assert sort_projects([], "name", desc=False) == []

    def test_does_not_mutate_input(self, projects: list[Project]) -> None:
        before = _codes(projects)
        sort_projects(projects, "budget", desc=True)
        assert _codes(projects) == before

    @pytest.mark.parametrize(
        ("column", "expected_asc"),
        [
            ("name", ["A", "B", "C"]),
            ("customer", ["A", "C", "B"]),
            ("state", ["C", "B", "A"]),
            ("budget", ["C", "B", "A"]),
            ("current_spent", ["C", "B", "A"]),
            ("current_progress", ["B", "C", "A"]),
            ("risk_count", ["A", "C", "B"]),
        ],
    )
    def test_column_both_directions(
        self, projects: list[Project], column: str, expected_asc: list[str]
    ) -> None:
        assert _codes(sort_projects(projects, column, desc=False)) == expected_asc
        assert _codes(sort_projects(projects, column, desc=True)) == list(
            reversed(expected_asc)
        )

    def test_name_is_case_insensitive(self, projects: list[Project]) -> None:
        # "beta" (lowercase) must sort between "Alpha" and "Gamma".
        assert _codes(sort_projects(projects, "name", desc=False)) == ["A", "B", "C"]

    def test_state_uses_lifecycle_order(self) -> None:
        items = [
            Project(code="done", state="Abgeschlossen"),
            Project(code="risk", state="Risiko"),
            Project(code="active", state="Aktiv"),
            Project(code="planned", state="Geplant"),
        ]
        assert _codes(sort_projects(items, "state", desc=False)) == [
            "planned",
            "active",
            "risk",
            "done",
        ]

    def test_missing_start_date_sorts_last_ascending(
        self, projects: list[Project]
    ) -> None:
        assert _codes(sort_projects(projects, "start_date", desc=False)) == [
            "C",
            "B",
            "A",
        ]

    def test_missing_start_date_sorts_last_descending(
        self, projects: list[Project]
    ) -> None:
        assert _codes(sort_projects(projects, "start_date", desc=True)) == [
            "B",
            "C",
            "A",
        ]

    def test_unknown_column_falls_back_to_name(self, projects: list[Project]) -> None:
        assert _codes(sort_projects(projects, "bogus", desc=False)) == ["A", "B", "C"]

    def test_ties_keep_name_order(self) -> None:
        items = [
            Project(code="Z", name_de="Zulu", budget=100),
            Project(code="A", name_de="Alpha", budget=100),
        ]
        assert _codes(sort_projects(items, "budget", desc=False)) == ["A", "Z"]
        assert _codes(sort_projects(items, "budget", desc=True)) == ["A", "Z"]

    def test_sort_columns_contract(self) -> None:
        assert DEFAULT_SORT_COLUMN == "name"
        assert set(SORT_COLUMNS) == {
            "name",
            "customer",
            "state",
            "start_date",
            "budget",
            "current_spent",
            "current_progress",
            "risk_count",
        }
