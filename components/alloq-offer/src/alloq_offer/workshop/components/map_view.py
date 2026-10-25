"""The story map: activity columns, slice rows and story cards."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.excel_grid import column_resize, resize_handle
from alloq_commons.components.toolbar import segmented
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.workshop.components.archive_dialog import (
    archive_button,
    archive_dialog,
)
from alloq_offer.workshop.components.map_list import story_list
from alloq_offer.workshop.components.map_proposal import (
    map_proposal,
    map_proposal_panel,
)
from alloq_offer.workshop.states.map_state import (
    INSERT_ACTIVITY,
    INSERT_SLICE,
    VIEW_LIST,
    VIEWS,
    MapState,
)
from alloq_offer.workshop.states.workshop_state import WorkshopState

SEARCH_PLACEHOLDER = "Stories suchen"
SEARCH_DEBOUNCE_MS = 250
SLICE_PLACEHOLDER = "Umsetzungsschnitte"
SKELETON_ONLY = "Nur Skeleton"
RESET_FILTERS = "Filter zurücksetzen"
NAME_PLACEHOLDER = "Name"
OK = "OK"
CANCEL = "Abbrechen"
ADD_ACTIVITY = "Aktivität hinzufügen"
ADD_SLICE = "Umsetzungsschnitt hinzufügen"
ADD_STORY = "Story hinzufügen"
SKELETON = "Skeleton"
DELETE_SLICE = "Umsetzungsschnitt löschen"
DELETE_SLICE_HINT = "Schnitt löschen – die Stories bleiben ohne Schnitt erhalten"
TOGGLE_SLICE = "Schnitt ein- oder ausklappen"
COLUMN_LINE = "1px solid var(--alloq-border-strong)"
"""Activity column lines; as strong as the month lines of the planning grid."""
COLUMN_WIDTHS_KEY = "aq-map-columns-"
"""Prefix of the localStorage key for this viewer's column widths per offer."""

Row = ObjectVar[dict[str, Any]]


def _story_card(story: Row) -> rx.Component:
    """Light blue card; hover and the selected story are styled in aq-workshop.css."""
    return rx.el.button(
        mn.stack(
            mn.group(
                mn.text(story["key"], fz="xs", c=theme.TEXT_MUTED, style=theme.NUMERIC),
                rx.cond(
                    story["skeleton"],
                    mn.badge(SKELETON, variant="outline", size="xs"),
                ),
                justify="space-between",
                wrap="nowrap",
            ),
            mn.text(story["title"], fw=600, fz="xs"),
            gap=2,
        ),
        type="button",
        on_click=MapState.select_story(story["id"]),
        custom_attrs={"data-selected": MapState.selected_id == story["id"].to_string()},
        class_name="aq-story-card",
    )


def _cell(cell: Row, slice_id: rx.Var) -> rx.Component:
    return mn.stack(
        rx.foreach(cell["stories"].to(list[dict[str, Any]]), _story_card),
        _add_story_form(cell, slice_id),
        gap=8,
        p=10,
        style={"borderLeft": COLUMN_LINE},
    )


def _add_story_form(cell: Row, slice_id: rx.Var) -> rx.Component:
    """Quick add at the bottom of a cell: type a title, Enter or the plus adds it.

    The cell's ids are hidden fields; the submit handler cannot read loop vars.
    """
    return rx.form(
        rx.el.input(type="hidden", name="task_id", value=cell["task_id"].to_string()),
        rx.el.input(type="hidden", name="slice_id", value=slice_id.to_string()),
        mn.text_input(
            name="title",
            placeholder=ADD_STORY,
            size="xs",
            right_section=mn.action_icon(
                rx.icon("plus", size=14),
                type="submit",
                variant="subtle",
                color="gray",
                size="sm",
                loading=MapState.saving_cell
                == cell["task_id"].to_string() + ":" + slice_id.to_string(),
                aria_label=ADD_STORY,
            ),
            right_section_pointer_events="all",
            custom_attrs={"maxLength": 300, "aria-label": ADD_STORY},
        ),
        on_submit=MapState.add_story,
        reset_on_submit=True,
        class_name="aq-add-story",
    )


def _band(row: Row, collapsed: rx.Var[bool]) -> rx.Component:
    """Full-width slice row like a planning block header; its left part stays put."""
    return mn.box(
        mn.group(
            _insert_edge("slice", row["index"].to(int), "aq-map-plus-inline"),
            mn.action_icon(
                rx.cond(
                    collapsed,
                    rx.icon("chevron-right", size=16, stroke_width=2),
                    rx.icon("chevron-down", size=16, stroke_width=2),
                ),
                variant="subtle",
                color="gray",
                size="sm",
                on_click=MapState.toggle_slice(row["slice_id"]),
                aria_label=TOGGLE_SLICE,
            ),
            rx.cond(
                row["editable"],
                mn.text_input(
                    default_value=row["title"],
                    key=row["title"].to(str),
                    on_blur=lambda value: MapState.rename_slice(row["slice_id"], value),  # ty: ignore[invalid-argument-type]
                    size="xs",
                    variant="unstyled",
                    custom_attrs={
                        "maxLength": 255,
                        "aria-label": "Name des Schnitts",
                        "title": row["title"],
                    },
                    class_name="aq-map-title",
                    w=280,
                ),
                mn.text(row["title"], fw=600, fz="13px", c=theme.TEXT_MUTED),
            ),
            mn.text(row["count_label"].to(str), fz="12px", c=theme.TEXT_MUTED),
            gap=6,
            wrap="nowrap",
            align="center",
            class_name="aq-band-pin",
        ),
        rx.cond(
            row["editable"],
            mn.box(
                mn.tooltip(
                    mn.action_icon(
                        rx.icon("x", size=14),
                        variant="subtle",
                        color="red",
                        size="sm",
                        on_click=MapState.delete_slice(row["slice_id"]),
                        aria_label=DELETE_SLICE,
                    ),
                    label=DELETE_SLICE_HINT,
                    with_arrow=True,
                    z_index=theme.PAGE_POPOVER_Z_INDEX,
                ),
                class_name="aq-band-end",
            ),
        ),
        class_name="aq-map-band",
    )


def _row(row: Row) -> rx.Component:
    collapsed = MapState.collapsed_slices.contains(row["slice_id"].to_string())
    return rx.fragment(
        _band(row, collapsed),
        rx.cond(
            collapsed,
            rx.fragment(),
            rx.box(
                rx.foreach(
                    row["cells"].to(list[dict[str, Any]]),
                    lambda cell: _cell(cell, row["slice_id"]),
                ),
                display="grid",
                grid_template_columns=MapState.grid_template,
                class_name="aq-map-row",
            ),
        ),
    )


def _column_title(column: Row) -> rx.Component:
    """Title shown on at most two lines; the text area over it edits it."""
    return mn.box(
        mn.text(column["title"], fz="xs", fw=600, lh="1.4", class_name="aq-clamp-view"),
        mn.textarea(
            default_value=column["title"],
            key=column["title"].to(str),
            on_blur=lambda value: MapState.rename_activity(column["id"], value),  # ty: ignore[invalid-argument-type]
            variant="unstyled",
            custom_attrs={
                "maxLength": 255,
                "aria-label": "Name der Aktivität",
                "title": column["title"],
            },
            class_name="aq-clamp-input",
        ),
        class_name="aq-clamp-edit",
    )


def _column(column: Row) -> rx.Component:
    """Activity header: editable title with its move and archive icons on the right."""
    return mn.group(
        _column_title(column),
        mn.group(
            mn.tooltip(
                mn.action_icon(
                    rx.icon("chevron-left", size=14),
                    variant="subtle",
                    color="gray",
                    size="sm",
                    disabled=column["first"],
                    on_click=MapState.move_activity(column["id"], -1),
                    aria_label="Nach links",
                ),
                label="Aktivität nach links verschieben",
                with_arrow=True,
                z_index=theme.PAGE_POPOVER_Z_INDEX,
            ),
            mn.tooltip(
                mn.action_icon(
                    rx.icon("chevron-right", size=14),
                    variant="subtle",
                    color="gray",
                    size="sm",
                    disabled=column["last"],
                    on_click=MapState.move_activity(column["id"], 1),
                    aria_label="Nach rechts",
                ),
                label="Aktivität nach rechts verschieben",
                with_arrow=True,
                z_index=theme.PAGE_POPOVER_Z_INDEX,
            ),
            mn.tooltip(
                mn.action_icon(
                    rx.icon("x", size=14),
                    variant="subtle",
                    color="red",
                    size="sm",
                    on_click=MapState.archive_activity(column["id"]),
                    aria_label="Aktivität archivieren",
                ),
                label="Aktivität archivieren (nur ohne Stories)",
                with_arrow=True,
                z_index=theme.PAGE_POPOVER_Z_INDEX,
            ),
            gap=0,
            wrap="nowrap",
        ),
        rx.cond(column["first"], _insert_edge("activity", 0, "aq-map-plus-xl")),
        _insert_edge("activity", column["index"].to(int) + 1, "aq-map-plus-x"),
        resize_handle(column["id"]),
        gap=4,
        wrap="nowrap",
        align="flex-start",
        p=10,
        pos="relative",
        style={"borderLeft": COLUMN_LINE},
    )


INSERT_TITLES = {INSERT_ACTIVITY: ADD_ACTIVITY, INSERT_SLICE: ADD_SLICE}


def _insert_edge(kind: str, index: rx.Var[int] | int, edge: str) -> rx.Component:
    """Plus on a grid edge; its popup names the activity or slice to insert."""
    title = INSERT_TITLES[kind]
    key = f"{kind}:" + rx.Var.create(index).to_string()
    return mn.popover(
        mn.popover.target(
            mn.action_icon(
                rx.icon("plus", size=12),
                variant="default",
                radius="xl",
                size=18,
                on_click=MapState.open_insert(key),
                aria_label=title,
                class_name=f"aq-map-plus {edge}",
            ),
        ),
        mn.popover.dropdown(
            rx.form(
                mn.stack(
                    mn.text(title, fz="13px", fw=650),
                    mn.text_input(
                        name="title",
                        placeholder=NAME_PLACEHOLDER,
                        size="xs",
                        data_autofocus=True,
                        custom_attrs={"maxLength": 255, "aria-label": title},
                    ),
                    mn.group(
                        mn.button(
                            CANCEL,
                            type="button",
                            variant="default",
                            size="xs",
                            on_click=MapState.close_insert,
                        ),
                        mn.button(OK, type="submit", size="xs"),
                        justify="flex-end",
                        gap=6,
                    ),
                    gap=8,
                ),
                # Only the name: the loop variable behind ``index`` does not
                # exist in the submit handler Reflex builds for the form.
                on_submit=MapState.submit_insert,
                reset_on_submit=True,
            ),
        ),
        opened=MapState.insert_at == key,
        on_close=MapState.close_insert,
        position="bottom",
        with_arrow=True,
        trap_focus=True,
        shadow="md",
        width=260,
        z_index=theme.PAGE_POPOVER_Z_INDEX,
    )


def _grid() -> rx.Component:
    return column_resize(
        rx.box(
            rx.box(
                rx.foreach(MapState.columns, _column),
                display="grid",
                grid_template_columns=MapState.grid_template,
                class_name="aq-map-head",
            ),
            rx.foreach(MapState.visible_rows, _row),
            class_name="aq-map-grid",
        ),
        storage_key=COLUMN_WIDTHS_KEY + WorkshopState.offer_id.to_string(),
        class_name="aq-map-scroll",
    )


def _footer() -> rx.Component:
    return mn.group(
        mn.box(map_proposal(), ml="auto"),
        gap=12,
        class_name="aq-map-footer",
    )


def _filter_select(
    data: rx.Var | list[str],
    value: rx.Var[list[str]],
    on_change: rx.event.EventType[list[str]],
    placeholder: str,
    label: rx.Var[str],
) -> rx.Component:
    return mn.multi_select(
        data=data,
        value=value,
        on_change=on_change,
        placeholder=placeholder,
        clearable=True,
        size="xs",
        w="11rem",
        class_name=rx.cond(
            value.length() > 0, "alloq-filter-ms has-mehr", "alloq-filter-ms"
        ),
        style={"--alloq-mehr": label},
    )


def _search() -> rx.Component:
    """Story search that asks the server once the person stops typing.

    The field is uncontrolled (a controlled one would jump back while the
    debounced event is on its way); a filter reset remounts it through ``key``.
    """
    return mn.text_input(
        placeholder=SEARCH_PLACEHOLDER,
        left_section=rx.icon("search", size=14),
        left_section_pointer_events="none",
        default_value=MapState.map_search,
        key=MapState.search_epoch.to_string(),
        on_change=lambda value: MapState.set_map_search(value).debounce(  # ty: ignore[invalid-argument-type]
            SEARCH_DEBOUNCE_MS
        ),
        size="xs",
        radius="md",
        w="200px",
        class_name="aq-toolbar-search",
        custom_attrs={"type": "search", "aria-label": SEARCH_PLACEHOLDER},
    )


def map_filter_row() -> rx.Component:
    """Filter bar of the map: view, story search, slices and skeleton filter."""
    return mn.group(
        segmented(MapState.view, MapState.set_view, VIEWS),
        _search(),
        _filter_select(
            MapState.slice_options,
            MapState.slice_filter,
            MapState.set_slice_filter,
            SLICE_PLACEHOLDER,
            MapState.slice_filter_label,
        ),
        mn.switch(
            label=SKELETON_ONLY,
            checked=MapState.skeleton_only,
            on_change=MapState.set_skeleton_only,
            color="blue",
            size="xs",
        ),
        rx.cond(
            MapState.is_filtered,
            mn.button(
                RESET_FILTERS,
                variant="subtle",
                color="gray",
                size="compact-xs",
                on_click=MapState.reset_filters,
            ),
        ),
        mn.group(
            archive_button(),
            mn.text(MapState.summary, fz="12px", c=theme.TEXT_MUTED),
            gap=8,
            ml="auto",
        ),
        gap=8,
        w="100%",
    )


def map_section() -> rx.Component:
    """Map grid or story list filling the pane, the open proposal and the footer."""
    return rx.fragment(
        rx.cond(MapState.view == VIEW_LIST, story_list(), _grid()),
        map_proposal_panel(),
        _footer(),
        archive_dialog(),
    )
