"""Resizable grid columns, shared by ExcelGrid (``resize_key``) and plain grids.

A column's width is the CSS variable ``--grid-col-<key>`` on the grid root. Use
:func:`column_width` in the grid template, put :func:`resize_handle` into the
column's header cell (it must be positioned) and give the root a storage key:
``excel_grid(..., resize_key=...)`` or :func:`column_resize` for other grids.
"""

from __future__ import annotations

from typing import Any

import reflex as rx
from reflex.vars.base import Var

from alloq_commons import theme
from alloq_commons.components.excel_grid.excel_grid import RESIZE_JSX_IMPORT

RESIZE_HANDLE_CLASS = "grid-col-resize"
RESIZE_HINT = "Breite ziehen · Doppelklick setzt zurück"


class ColumnResize(rx.Component):
    """Plain div that owns the column width variables of the grid inside."""

    library = RESIZE_JSX_IMPORT
    tag = "ColumnResize"

    storage_key: Var[str]
    """localStorage key under which this viewer's widths are kept."""


column_resize = ColumnResize.create


def column_width(key: Any, default_px: int) -> Any:
    """Grid track for a resizable column: its stored width or the default."""
    if isinstance(key, Var):
        return "var(--grid-col-" + key.to_string() + f", {default_px}px)"
    return f"var(--grid-col-{key}, {default_px}px)"


def resize_handle(key: Any) -> rx.Component:
    """Drag handle on the right edge of a header cell."""
    return rx.el.div(
        custom_attrs={"data-col-resize": key, "title": RESIZE_HINT},
        class_name=RESIZE_HANDLE_CLASS,
        style={
            "position": "absolute",
            "top": "0",
            "right": "-4px",
            "bottom": "0",
            "width": "8px",
            "zIndex": "4",
            "cursor": "col-resize",
            "touchAction": "none",
            "_hover": {
                "background": f"linear-gradient(to right, transparent 3px, "
                f"{theme.ACCENT} 3px, {theme.ACCENT} 5px, transparent 5px)",
            },
        },
    )
