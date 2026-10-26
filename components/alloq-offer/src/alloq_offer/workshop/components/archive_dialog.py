"""Dialog with the archived stories of the map and their way back."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.modal_layout import MODAL_CLASS, MODAL_OVERLAY
from alloq_commons.components.toolbar import toolbar_search
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.workshop.states.map_state import MapState

TITLE = "Archivierte Stories"
EMPTY = "Es gibt keine archivierten Stories."
NO_MATCH = "Keine Story passt zur Suche."
HINT = "Wählen Sie pro Story die Aufgabe, unter der sie wieder erscheint."
SEARCH_PLACEHOLDER = "Schlüssel, Titel oder Ort suchen"
TASK_PLACEHOLDER = "Aufgabe wählen"
RESTORE = "Wiederherstellen"
SELECT_WIDTH = 220
ROW_PX = 58
ROW_GAP_PX = 6
VISIBLE_ROWS = 4
LIST_HEIGHT = f"{VISIBLE_ROWS * ROW_PX + (VISIBLE_ROWS - 1) * ROW_GAP_PX}px"
"""Fixed height for four rows, so searching never resizes the dialog."""
ROW_STYLE = {
    "border": f"1px solid {theme.BORDER}",
    "borderRadius": "8px",
    "background": theme.SURFACE,
}

Story = ObjectVar[dict[str, Any]]


def _entry(story: Story) -> rx.Component:
    return mn.group(
        mn.stack(
            mn.group(
                mn.text(story["key"], fz="xs", c=theme.TEXT_MUTED, style=theme.NUMERIC),
                mn.text(story["where"], fz="xs", c=theme.TEXT_MUTED, truncate="end"),
                gap=8,
                wrap="nowrap",
            ),
            mn.text(story["title"], fw=600, fz="sm"),
            gap=2,
            style={"flex": 1, "minWidth": 0},
        ),
        mn.select(
            data=MapState.task_groups,
            value=story["task"].to(str),
            placeholder=TASK_PLACEHOLDER,
            on_change=lambda picked: MapState.set_restore_task(  # ty: ignore[invalid-argument-type]
                story["id"], picked
            ),
            allow_deselect=False,
            searchable=True,
            size="xs",
            w=SELECT_WIDTH,
        ),
        mn.action_icon(
            rx.icon("archive-restore", size=16),
            variant="subtle",
            size="md",
            disabled=story["task"].to(str) == "",
            on_click=MapState.restore_story(story["id"]),
            aria_label=RESTORE,
            custom_attrs={"title": RESTORE},
        ),
        wrap="nowrap",
        gap=10,
        h=ROW_PX,
        py=8,
        pl=12,
        pr=8,
        style=ROW_STYLE,
    )


def archive_button() -> rx.Component:
    """Opens the dialog; shows how many stories are archived."""
    return mn.button(
        MapState.archive_label,
        variant="subtle",
        color="gray",
        size="compact-xs",
        left_section=rx.icon("archive-restore", size=14),
        on_click=MapState.open_archive,
    )


def _list() -> rx.Component:
    return mn.scroll_area(
        rx.cond(
            MapState.archived_rows.length() > 0,
            mn.stack(
                rx.foreach(MapState.archived_rows.to(list[dict[str, Any]]), _entry),
                gap=ROW_GAP_PX,
            ),
            mn.text(NO_MATCH, fz="13px", c=theme.TEXT_MUTED, ta="center", py=24),
        ),
        # mn.scroll_area hands ``h`` to css as is, which is no CSS property.
        style={"height": LIST_HEIGHT},
        type="auto",
        scrollbars="y",
        offset_scrollbars="y",
    )


def _body() -> rx.Component:
    """Content in the shared modal padding; the header X closes the dialog."""
    return rx.flex(
        rx.box(
            rx.cond(
                MapState.archived.length() > 0,
                mn.stack(
                    mn.text(HINT, fz="13px", c=theme.TEXT_MUTED),
                    toolbar_search(
                        MapState.archive_search,
                        MapState.set_archive_search,
                        SEARCH_PLACEHOLDER,
                        width="100%",
                    ),
                    _list(),
                    gap="sm",
                    pb=18,
                ),
                mn.text(EMPTY, fz="13px", c=theme.TEXT_MUTED, pb=18),
            ),
            class_name="alloq-modal-scroll",
        ),
        direction="column",
        class_name="alloq-modal-inner",
    )


def archive_dialog() -> rx.Component:
    return mn.modal(
        _body(),
        title=TITLE,
        opened=MapState.archive_open,
        on_close=MapState.close_archive,
        size="xl",
        centered=True,
        class_name=MODAL_CLASS,
        overlay_props=MODAL_OVERLAY,
    )
