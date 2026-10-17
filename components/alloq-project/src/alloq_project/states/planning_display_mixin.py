"""Display settings of the planning grids; mixed into `PlanningStore`."""

from __future__ import annotations

from typing import TYPE_CHECKING

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


class PlanningDisplayState(rx.State, mixin=True):
    """Row density and column layout of the planning grids.

    A mixin rather than a substate: the grid components read these vars next to
    `PlanningStore` vars, and the density must survive reloads per browser.
    """

    if TYPE_CHECKING:  # Provided by PlanningStore.
        weeks: list[WeekColumn]

    grid_density: str = rx.LocalStorage(NORMAL, name="alloq_planning_density")

    @rx.event
    def toggle_grid_density(self) -> None:
        self.grid_density = NORMAL if self.grid_density == COMPACT else COMPACT

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
    def month_start_keys(self) -> list[str]:
        return [w.key for w in self.weeks if w.is_month_start]
