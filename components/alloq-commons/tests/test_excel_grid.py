"""Tests for the reusable ExcelGrid Reflex wrapper."""

import reflex as rx
from alloq_commons.components.excel_grid import (
    ExcelGrid,
    excel_grid,
    grid_cell_attrs,
    grid_row_attrs,
)


class _GridState(rx.State):
    revision: int = 0

    @rx.event
    def commit(self, changes: list[dict]) -> None:
        pass

    @rx.event
    def reject(self, count: int) -> None:
        pass

    @rx.event
    def save(self) -> None:
        pass


def test_attr_helpers() -> None:
    assert grid_row_attrs("r1", "b1") == {"data-row-key": "r1", "data-block": "b1"}
    assert grid_cell_attrs("r1|c1", "c1", 2.5) == {
        "data-cell-key": "r1|c1",
        "data-col": "c1",
        "data-value": 2.5,
    }


def test_renders_with_events_and_props() -> None:
    component = excel_grid(
        rx.el.div(
            rx.el.div("1", custom_attrs=grid_cell_attrs("r|c", "c", 1)),
            custom_attrs=grid_row_attrs("r"),
        ),
        id="grid",
        revision=_GridState.revision,
        dirty=True,
        decimals=1,
        on_commit=_GridState.commit,
        on_reject=_GridState.reject,
        on_save=_GridState.save,
    )
    assert isinstance(component, ExcelGrid)
    rendered = str(component)
    assert rendered.startswith("jsx(ExcelGrid,")
    for fragment in ("onCommit", "onReject", "onSave", "decimals:1", "data-cell-key"):
        assert fragment in rendered
    imports = component._get_all_imports()
    assert any(lib.endswith("excel_grid/excel_grid.jsx") for lib in imports)
