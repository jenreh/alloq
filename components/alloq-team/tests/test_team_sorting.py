"""Tests for the team list sorting helper."""

from alloq_team.states.team_list_state import (
    DEFAULT_SORT_COLUMN,
    SORT_COLUMNS,
    TeamDetail,
    sort_team_rows,
)


def _rows() -> list[TeamDetail]:
    return [
        TeamDetail(
            id=1,
            name="Zoë",
            subtitle="",
            initials="Z",
            color="#000000",
            role="Developer",
            hours=32,
            load_percent=80,
            free_days=5,
            project_count=2,
        ),
        TeamDetail(
            id=2,
            name="Ada",
            subtitle="",
            initials="A",
            color="#000000",
            role="Architect",
            hours=40,
            load_percent=100,
            free_days=1,
            project_count=3,
        ),
        TeamDetail(
            id=3,
            name="Mira",
            subtitle="",
            initials="M",
            color="#000000",
            role="Developer",
            hours=20,
            load_percent=50,
            free_days=10,
            project_count=1,
        ),
    ]


def test_sort_team_rows_by_each_column() -> None:
    rows = _rows()
    expected_ascending = {
        "name": [2, 3, 1],
        "role": [2, 3, 1],
        "hours": [3, 1, 2],
        "load_percent": [3, 1, 2],
        "free_days": [2, 1, 3],
        "project_count": [3, 1, 2],
    }
    expected_descending = {
        **{column: list(reversed(ids)) for column, ids in expected_ascending.items()},
        "role": [3, 1, 2],
    }

    for column, expected in expected_ascending.items():
        assert [row.id for row in sort_team_rows(rows, column, False)] == expected
        assert [row.id for row in sort_team_rows(rows, column, True)] == list(
            expected_descending[column]
        )


def test_sort_team_rows_does_not_mutate_input() -> None:
    rows = _rows()

    sort_team_rows(rows, "hours", True)

    assert [row.id for row in rows] == [1, 2, 3]


def test_sort_contract() -> None:
    assert DEFAULT_SORT_COLUMN == "name"
    assert set(SORT_COLUMNS) == {
        "name",
        "role",
        "hours",
        "load_percent",
        "free_days",
        "project_count",
    }
