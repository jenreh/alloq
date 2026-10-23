"""The price sheet exposes typed cells and the existing Excel controller."""

import json
from collections.abc import Iterator

import pytest
import reflex as rx
from alloq_commons.components.price_list import (
    edit_actions,
    price_list_editor,
    price_list_toolbar,
    price_sheet,
)


def _walk(component: rx.Component) -> Iterator[rx.Component]:
    yield component
    for child in component.children:
        yield from _walk(child)


def test_document_navigation_is_in_the_header() -> None:
    header = " ".join(str(control) for control in price_list_toolbar())
    for marker in (
        "list_options",
        "request_action",
        "duplicate",
        "new",
        "toggle_archive",
        "save",
        "discard",
    ):
        assert marker in header
    assert "aq-icon-btn" in header
    assert "request_action" not in str(price_list_editor())


def test_template_controls_are_removed() -> None:
    rendered = str(price_list_editor()) + " ".join(
        str(control) for control in price_list_toolbar()
    )
    assert "template_key" not in rendered
    assert "set_template" not in rendered


@pytest.mark.parametrize("comparison", [False, True])
def test_frozen_headers_stay_above_scrolling_headers(comparison: bool) -> None:
    headers = [
        node
        for node in _walk(price_sheet(comparison=comparison))
        if node.tag == "Table.Th" and "zIndex" in node.style
    ]
    frozen = headers[:2]
    scrolling = [header for header in headers[2:] if "right" not in header.style]
    assert len(frozen) == 2
    assert scrolling
    la_width = json.loads(str(frozen[0].style["width"]))
    for header, left in zip(frozen, ["0px", la_width], strict=True):
        assert json.loads(str(header.style["position"])) == "sticky"
        assert json.loads(str(header.style["left"])) == left
        assert json.loads(str(header.style["zIndex"])) > max(
            json.loads(str(other.style["zIndex"])) for other in scrolling
        )


def test_price_sheet_has_grid_and_document_controls() -> None:
    rendered = str(price_list_editor())
    for marker in (
        "ExcelGrid",
        "onDiscard",
        "data-read-only",
        "data-cell-type",
        "minimum_daily",
        "apply_cell_changes",
        "resolve_pending",
        "set_role",
        "save",
        "discard",
    ):
        assert marker in rendered


@pytest.mark.parametrize("comparison", [False, True])
def test_frozen_cells_keep_a_visible_right_border(comparison: bool) -> None:
    cells = [
        node
        for node in _walk(price_sheet(comparison=comparison))
        if node.tag in {"Table.Th", "Table.Td"} and "left" in node.style
    ]
    assert {cell.tag for cell in cells} == {"Table.Th", "Table.Td"}
    for cell in cells:
        assert json.loads(str(cell.style.get("boxShadow", '""'))) == (
            "inset -1px 0 0 var(--alloq-border)"
        )


def test_save_is_an_icon_before_the_new_primary_action() -> None:
    actions = edit_actions()
    assert actions[-1].tag == "Button"
    assert '"Neu"' in str(actions[-1])
    assert actions[-2].tag == "Tooltip"
    assert ".save" in str(actions[-2])
    buttons = [
        node for action in actions for node in _walk(action) if node.tag == "Button"
    ]
    assert len(buttons) == 1
    assert "Speichern" not in str(buttons[0])


def test_readers_switch_lists_and_admins_get_the_edit_actions() -> None:
    select, actions = (str(control) for control in price_list_toolbar())
    assert "is_admin" in select
    assert "open_list" in select
    assert "request_action" in select
    assert "is_admin" in actions
    assert "toggle_archive" in actions


def test_sheet_and_settings_are_read_only_without_admin() -> None:
    rendered = str(price_list_editor())
    assert "fieldset" in rendered
    assert "is_admin" in rendered
    grid = next(node for node in _walk(price_sheet()) if node.tag == "ExcelGrid")
    assert "is_admin" in str(grid.read_only)
    assert str(price_sheet(comparison=True)).count("is_admin") == 0
