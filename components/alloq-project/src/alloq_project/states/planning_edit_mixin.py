"""Unsaved cell edits of the planning grid; mixed into `PlanningStore`."""

import reflex as rx


class PlanningEditMixin(rx.State, mixin=True):
    """Cell values, their saved copy and the unsaved edits between them."""

    cells: rx.Field[dict[str, float]] = rx.field(default_factory=dict)
    saved_cells: rx.Field[dict[str, float]] = rx.field(default_factory=dict)
    dirty_keys: rx.Field[list[str]] = rx.field(default_factory=list)
    # Unsaved edits whose row/week is not part of the loaded time range.
    hidden_edits: rx.Field[dict[str, float]] = rx.field(default_factory=dict)
    grid_revision: rx.Field[int] = rx.field(0)
    is_saving: rx.Field[bool] = rx.field(False)

    @rx.var(cache=True)
    def has_dirty(self) -> bool:
        return len(self.dirty_keys) > 0 or len(self.hidden_edits) > 0

    def _unsaved_edits(self) -> dict[str, float]:
        """All unsaved edits, including those outside the loaded range."""
        return {
            **self.hidden_edits,
            **{key: self.cells.get(key, 0.0) for key in self.dirty_keys},
        }

    @rx.event
    def discard_changes(self) -> None:
        """Forget all unsaved edits and show the saved values again."""
        if self.is_saving:
            return
        self.cells = dict(self.saved_cells)
        self.dirty_keys = []
        self.hidden_edits = {}
        # A new revision also clears the grid's undo history and pending edits.
        self.grid_revision += 1
