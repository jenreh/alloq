"""Reflex wrapper for the reusable Excel-like grid controller.

``excel_grid`` wraps any Reflex-rendered grid markup and adds Excel-style
selection, keyboard navigation, in-cell editing, clipboard (TSV), fill and
undo/redo entirely in the browser. Only committed batches reach the server
through ``on_commit`` as ``[{"key": cell_key, "value": number}, ...]``.

Mark up the children with :func:`grid_row_attrs` on every editable row and
:func:`grid_cell_attrs` on every editable cell. Rows sharing a ``block`` form
one data region (Ctrl+Arrow / Ctrl+A jump per block).
"""

from __future__ import annotations

from typing import Any

import reflex as rx
from reflex.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex.vars.base import Var

rx.asset("grid_logic.js", shared=True)
_JSX_IMPORT = rx.asset("excel_grid.jsx", shared=True).importable_path


class ExcelGrid(rx.Component):
    """Excel-like interaction layer around a numeric grid."""

    library = _JSX_IMPORT
    tag = "ExcelGrid"

    revision: Var[int]
    """Bump to reset undo/redo history (e.g. after a reload)."""

    dirty: Var[bool]
    """Warn before leaving the page while True."""

    grid_label: Var[str]
    min_value: Var[float]
    max_value: Var[float]
    decimals: Var[int]
    decimal_separator: Var[str]
    invalid_message: Var[str]

    on_commit: EventHandler[passthrough_event_spec(list[dict[str, Any]])]
    on_reject: EventHandler[passthrough_event_spec(int)]
    on_save: EventHandler[no_args_event_spec]


excel_grid = ExcelGrid.create


def grid_row_attrs(row_key: Any, block: Any = "") -> dict[str, Any]:
    """``custom_attrs`` for an editable row element."""
    return {"data-row-key": row_key, "data-block": block}


def grid_cell_attrs(cell_key: Any, col: Any, value: Any) -> dict[str, Any]:
    """``custom_attrs`` for an editable cell element."""
    return {"data-cell-key": cell_key, "data-col": col, "data-value": value}
