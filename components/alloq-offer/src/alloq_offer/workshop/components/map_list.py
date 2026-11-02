"""The story map as a list: one line per story, edited like a spreadsheet."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.excel_grid import (
    column_width,
    excel_grid,
    grid_cell_attrs,
    grid_row_attrs,
    resize_handle,
)
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.workshop.states.map_state import MapState
from alloq_offer.workshop.states.workshop_state import WorkshopState

LIST_LABEL = "Story-Liste"
DETAILS = "Details öffnen"
LIST_COLUMNS = (
    ("activity", "Aktivität", 180, 0),
    ("title", "Story", 240, 300),
    ("story", "User Story", 420, 1000),
    ("description", "Beschreibung", 320, 4000),
)
"""Column key, header, default width in px and text limit (0: read only)."""
DETAILS_WIDTH = "44px"
COLUMN_WIDTHS_KEY = "aq-story-list-columns-"
"""Prefix of the localStorage key for this viewer's column widths per offer."""
_TRACKS = [column_width(key, width) for key, _, width, _ in LIST_COLUMNS]
# The last text column also takes the space left over.
TEMPLATE = " ".join([*_TRACKS[:-1], f"minmax({_TRACKS[-1]}, 1fr)", DETAILS_WIDTH])

Row = ObjectVar[dict[str, Any]]


def _cell(row: Row, column: str, limit: int) -> rx.Component:
    value = row[column].to(str)
    attrs = grid_cell_attrs(row["id"].to_string() + "|" + column, column, value)
    attrs.update(
        {
            "data-cell-type": "text",
            "data-read-only": "false" if limit else "true",
            "data-max-length": limit or 255,
            "title": value,
        }
    )
    return mn.box(
        value,
        custom_attrs=attrs,
        class_name="aq-list-cell",
        c=theme.TEXT if limit else theme.TEXT_MUTED,
    )


def _row(row: Row) -> rx.Component:
    return mn.box(
        *(_cell(row, column, limit) for column, _, _, limit in LIST_COLUMNS),
        mn.box(
            mn.action_icon(
                rx.icon("panel-right-open", size=15),
                variant="subtle",
                color="gray",
                size="sm",
                on_click=MapState.select_story(row["id"]),
                aria_label=DETAILS,
                custom_attrs={"title": DETAILS},
            ),
            class_name="aq-list-details",
        ),
        custom_attrs={
            **grid_row_attrs(row["id"].to_string(), "stories"),
            "data-selected": MapState.selected_id == row["id"].to_string(),
        },
        class_name="aq-list-row",
        style={"gridTemplateColumns": TEMPLATE},
    )


def _header() -> rx.Component:
    return mn.box(
        *(
            mn.box(title, resize_handle(key), class_name="aq-list-head-cell")
            for key, title, _, _ in LIST_COLUMNS
        ),
        mn.box(class_name="aq-list-head-cell"),
        class_name="aq-list-head",
        custom_attrs={"data-grid-header": "true"},
        style={"gridTemplateColumns": TEMPLATE},
    )


def story_list() -> rx.Component:
    """Stories of the visible rows; title, sentence and description are editable."""
    return excel_grid(
        _header(),
        rx.foreach(MapState.list_rows, _row),
        id="story-list-grid",
        grid_label=LIST_LABEL,
        revision=MapState.revision,
        dirty=False,
        saving=False,
        navigation_guard=False,
        resize_key=COLUMN_WIDTHS_KEY + WorkshopState.offer_id.to_string(),
        on_commit=MapState.apply_list_changes,
        on_reject=MapState.notify_rejected,
        class_name="aq-map-scroll aq-story-list",
        style={"outline": "none"},
    )
