"""Display settings of the planning grids; mixed into `PlanningStore`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import reflex as rx
from alloq_project.states.planning_models import (
    COMPACT_WEEK_COL_PX,
    LABEL_COL_PX,
    WEEK_COL_PX,
)

if TYPE_CHECKING:
    from alloq_project.states.planning_models import WeekColumn

NORMAL = "normal"
COMPACT = "kompakt"
DAYS_PER_WEEK = 7
HOLIDAY_COLOR_VAR = "var(--aq-holiday)"


def holiday_bands(days: list[int]) -> str:
    """CSS image with one plain band per holiday (0 = Monday) across a week cell."""
    bands = []
    for day in days:
        start = day * 100 / DAYS_PER_WEEK
        end = (day + 1) * 100 / DAYS_PER_WEEK
        bands.append(
            f"linear-gradient(to right, transparent {start:.4f}%, "
            f"{HOLIDAY_COLOR_VAR} {start:.4f}% {end:.4f}%, transparent {end:.4f}%)"
        )
    return ", ".join(bands)


class PlanningDisplayState(rx.State, mixin=True):
    """Row density and column layout of the planning grids.

    A mixin rather than a substate: the grid components read these vars next to
    `PlanningStore` vars. The density is kept per browser by `PlanningStore`.
    """

    if TYPE_CHECKING:  # Provided by PlanningStore.
        weeks: list[WeekColumn]

        def _store_view_settings(self) -> Any: ...

    grid_density: rx.Field[str] = rx.field(NORMAL)

    @rx.event
    def toggle_grid_density(self) -> Any:
        self.grid_density = NORMAL if self.grid_density == COMPACT else COMPACT
        return self._store_view_settings()

    @rx.var(cache=True)
    def is_compact(self) -> bool:
        return self.grid_density == COMPACT

    @rx.var(cache=True)
    def week_col_px(self) -> int:
        return COMPACT_WEEK_COL_PX if self.grid_density == COMPACT else WEEK_COL_PX

    @rx.var(cache=True)
    def table_width(self) -> str:
        return f"{LABEL_COL_PX + len(self.weeks) * self.week_col_px}px"

    @rx.var(cache=True)
    def grid_template_columns(self) -> str:
        return f"{LABEL_COL_PX}px repeat({len(self.weeks)}, {self.week_col_px}px)"

    @rx.var(cache=True)
    def holiday_backgrounds(self) -> dict[str, str]:
        """Holiday bands per week key; weeks without holidays are left out."""
        return {
            w.key: holiday_bands(w.holiday_days) for w in self.weeks if w.holiday_days
        }

    @rx.var(cache=True)
    def month_start_keys(self) -> list[str]:
        return [w.key for w in self.weeks if w.is_month_start]
