"""The story map: activity columns, slice rows and story cards."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.workshop.components.map_proposal import map_proposal
from alloq_offer.workshop.states.map_state import MapState

MAP_TITLE = "Story Map"
ADD_ACTIVITY = "Aktivität hinzufügen"
ADD_SLICE = "Umsetzungsschnitt hinzufügen"
ADD_STORY = "+ Story"
SKELETON = "Skeleton"
CORNER_LABELS = ("Aktivität", "Aufgabe")
SCOPE_COLORS = {
    "offen": "gray",
    "angeboten": "green",
    "option": "yellow",
    "ausgeschlossen": "red",
}

Row = ObjectVar[dict[str, Any]]


def scope_badge(scope: rx.Var) -> rx.Component:
    return mn.badge(
        scope,
        variant="light",
        size="sm",
        color=rx.match(scope, *SCOPE_COLORS.items(), "gray"),  # ty: ignore[invalid-argument-type]
    )


def _story_card(story: Row) -> rx.Component:
    selected = MapState.selected_id == story["id"].to(str)
    return mn.stack(
        rx.el.button(
            mn.stack(
                mn.group(
                    mn.text(
                        story["key"], fz="11.5px", c=theme.TEXT_MUTED, ff="monospace"
                    ),
                    rx.cond(
                        story["skeleton"],
                        mn.badge(SKELETON, variant="outline", size="xs"),
                    ),
                    justify="space-between",
                    wrap="nowrap",
                ),
                mn.text(story["title"], fw=600, fz="13px"),
                mn.group(scope_badge(story["scope"]), gap=6),
                mn.text(story["meta"], fz="11.5px", c=theme.TEXT_MUTED),
                gap=6,
            ),
            type="button",
            on_click=MapState.select_story(story["id"]),
            style={
                "textAlign": "left",
                "border": "0",
                "background": "transparent",
                "padding": "10px",
                "width": "100%",
                "cursor": "pointer",
                "font": "inherit",
                "color": "inherit",
            },
        ),
        style={
            "borderRadius": "10px",
            "background": theme.SURFACE,
            "boxShadow": rx.cond(
                selected,
                f"0 0 0 2px {theme.ACCENT}",
                f"0 0 0 1px {theme.BORDER}",
            ),
        },
    )


def _cell(cell: Row, slice_id: rx.Var) -> rx.Component:
    return mn.stack(
        rx.foreach(cell["stories"].to(list[dict[str, Any]]), _story_card),
        mn.button(
            ADD_STORY,
            variant="subtle",
            color="gray",
            size="compact-xs",
            on_click=MapState.add_story(cell["task_id"], slice_id),
        ),
        gap=8,
        p=10,
        style={"borderLeft": f"1px solid {theme.SEPARATOR}"},
    )


def _row(row: Row) -> rx.Component:
    return rx.box(
        mn.stack(
            rx.cond(
                row["editable"],
                mn.text_input(
                    default_value=row["title"],
                    key=row["title"].to(str),
                    on_blur=lambda value: MapState.rename_slice(row["slice_id"], value),  # ty: ignore[invalid-argument-type]
                    size="xs",
                    variant="unstyled",
                    custom_attrs={"maxLength": 255, "aria-label": "Name des Schnitts"},
                    class_name="aq-map-title",
                ),
                mn.text(row["title"], fw=600, fz="13px", c=theme.TEXT_MUTED),
            ),
            p=10,
        ),
        rx.foreach(
            row["cells"].to(list[dict[str, Any]]),
            lambda cell: _cell(cell, row["slice_id"]),
        ),
        display="grid",
        grid_template_columns=MapState.grid_template,
        style={"borderBottom": f"1px solid {theme.SEPARATOR}"},
    )


def _column(column: Row) -> rx.Component:
    return mn.stack(
        mn.text_input(
            default_value=column["title"],
            key=column["title"].to(str),
            on_blur=lambda value: MapState.rename_activity(column["id"], value),  # ty: ignore[invalid-argument-type]
            size="xs",
            variant="unstyled",
            custom_attrs={"maxLength": 255, "aria-label": "Name der Aktivität"},
            class_name="aq-map-title",
        ),
        mn.text(column["tasks"], fz="12px", c=theme.TEXT_MUTED),
        mn.group(
            mn.action_icon(
                rx.icon("chevron-left", size=14),
                variant="subtle",
                color="gray",
                size="sm",
                disabled=column["first"],
                on_click=MapState.move_activity(column["id"], -1),
                aria_label="Nach links",
            ),
            mn.action_icon(
                rx.icon("chevron-right", size=14),
                variant="subtle",
                color="gray",
                size="sm",
                disabled=column["last"],
                on_click=MapState.move_activity(column["id"], 1),
                aria_label="Nach rechts",
            ),
            mn.action_icon(
                rx.icon("x", size=14),
                variant="subtle",
                color="red",
                size="sm",
                on_click=MapState.archive_activity(column["id"]),
                aria_label="Aktivität archivieren",
            ),
            gap=2,
        ),
        gap=4,
        p=10,
        style={"borderLeft": f"1px solid {theme.SEPARATOR}"},
    )


def _add_form(placeholder: str, handler: rx.event.EventType) -> rx.Component:
    return rx.form(
        mn.text_input(
            name="title",
            placeholder=placeholder,
            size="xs",
            custom_attrs={"maxLength": 255, "aria-label": placeholder},
        ),
        on_submit=handler,
        reset_on_submit=True,
    )


def _grid() -> rx.Component:
    return rx.box(
        rx.box(
            rx.box(
                mn.stack(
                    *(
                        mn.text(label, fz="12px", fw=600, c=theme.TEXT_MUTED)
                        for label in CORNER_LABELS
                    ),
                    gap=4,
                    p=10,
                    justify="flex-end",
                ),
                rx.foreach(MapState.columns, _column),
                display="grid",
                grid_template_columns=MapState.grid_template,
                style={
                    "background": theme.SURFACE_MUTED,
                    "borderBottom": f"1px solid {theme.BORDER}",
                },
            ),
            rx.foreach(MapState.rows, _row),
            style={"minWidth": MapState.grid_min_width},
        ),
        style={"overflowX": "auto", **theme.CARD},
    )


def map_section() -> rx.Component:
    return mn.stack(
        mn.group(
            mn.text(MAP_TITLE, fw=650, fz="14px"),
            mn.text(MapState.summary, fz="12px", c=theme.TEXT_MUTED),
            gap=14,
        ),
        _grid(),
        mn.group(
            _add_form(ADD_ACTIVITY, MapState.add_activity),
            _add_form(ADD_SLICE, MapState.add_slice),
            gap=12,
        ),
        rx.cond(MapState.has_map, map_proposal()),
        gap=12,
    )
