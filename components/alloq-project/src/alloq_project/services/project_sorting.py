"""Client-side sorting for the project list view."""

from collections.abc import Callable
from typing import Any

from alloq_commons.entities.project import ProjectStateEnum
from alloq_commons.models.project import Project

DEFAULT_SORT_COLUMN = "name"

_STATE_ORDER: dict[str, int] = {
    ProjectStateEnum.PLANNED.value: 0,
    ProjectStateEnum.ACTIVE.value: 1,
    ProjectStateEnum.AT_RISK.value: 2,
    ProjectStateEnum.COMPLETED.value: 3,
}

_SORT_KEYS: dict[str, Callable[[Project], Any]] = {
    "name": lambda p: p.name_de.casefold(),
    "customer": lambda p: p.customer.casefold(),
    "state": lambda p: _STATE_ORDER.get(p.state, len(_STATE_ORDER)),
    "start_date": lambda p: p.start_date,
    "budget": lambda p: p.budget,
    "current_spent": lambda p: p.current_spent,
    "current_progress": lambda p: p.current_progress,
    "risk_count": lambda p: p.risk_count,
}

SORT_COLUMNS: tuple[str, ...] = tuple(_SORT_KEYS)


def sort_projects(projects: list[Project], column: str, desc: bool) -> list[Project]:
    """Return projects sorted by ``column``; ties keep ascending name order.

    Projects without a value for the column (e.g. no start date) always come last.
    Unknown columns fall back to sorting by name.
    """
    key = _SORT_KEYS.get(column, _SORT_KEYS[DEFAULT_SORT_COLUMN])
    by_name = sorted(projects, key=_SORT_KEYS[DEFAULT_SORT_COLUMN])
    with_value = [p for p in by_name if key(p) is not None]
    without_value = [p for p in by_name if key(p) is None]
    return sorted(with_value, key=key, reverse=desc) + without_value
