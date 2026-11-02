"""Tests for the reusable ExcelGrid Reflex wrapper."""

import json

import reflex as rx
from alloq_commons.components.excel_grid import (
    RESIZE_HANDLE_CLASS,
    RESIZE_HINT,
    ExcelGrid,
    column_resize,
    column_width,
    excel_grid,
    grid_cell_attrs,
    grid_row_attrs,
    resize_handle,
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
        saving=False,
        decimals=1,
        leave_title="Unsaved",
        on_commit=_GridState.commit,
        on_reject=_GridState.reject,
        on_save=_GridState.save,
        on_discard=_GridState.save,
    )
    assert isinstance(component, ExcelGrid)
    rendered = str(component)
    assert rendered.startswith("jsx(ExcelGrid,")
    for fragment in (
        "onCommit",
        "onReject",
        "onSave",
        "onDiscard",
        "decimals:1",
        "saving:false",
        'leaveTitle:"Unsaved"',
        "data-cell-key",
    ):
        assert fragment in rendered
    imports = component._get_all_imports()
    assert any(lib.endswith("excel_grid/excel_grid.jsx") for lib in imports)


def test_column_width_reads_the_resize_variable() -> None:
    assert column_width("title", 240) == "var(--grid-col-title, 240px)"
    width = column_width(rx.Var.create("12"), 230)
    assert "--grid-col-" in str(width)
    assert "230px" in str(width)


def test_resize_handle_marks_its_column() -> None:
    rendered = str(resize_handle("title"))
    assert "data-col-resize" in rendered
    assert RESIZE_HANDLE_CLASS in rendered
    assert json.dumps(RESIZE_HINT)[1:-1] in rendered


def test_resizable_grids_pass_their_storage_key() -> None:
    grid = str(
        excel_grid(
            rx.el.div(resize_handle("a")),
            id="g",
            resize_key="list-cols",
            on_commit=_GridState.commit,
        )
    )
    assert "resizeKey" in grid
    assert "list-cols" in grid
    wrapper = str(column_resize(rx.el.div("x"), storage_key="map-cols"))
    assert "ColumnResize" in wrapper
    assert "storageKey" in wrapper
