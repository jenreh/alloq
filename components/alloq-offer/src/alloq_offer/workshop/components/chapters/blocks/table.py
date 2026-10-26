"""Table chapters: a plain grid; cells are edited in place when selected."""

import reflex as rx
from alloq_commons import theme

import appkit_mantine as mn
from alloq_offer.workshop.components.chapters.blocks import Row
from alloq_offer.workshop.components.chapters.editor import (
    floating_toolbar,
    tool_button,
    toolbar_separator,
)
from alloq_offer.workshop.states.chapter_state import ChapterState

ADD_ROW = "+ Zeile"
ADD_COLUMN = "+ Spalte"
AI_LABEL = "KI-Vorschlag"
REMOVE_ROW = "Zeile entfernen"
EMPTY = "Die Tabelle hat noch keine Zeilen."
CELL_CLASS = "aq-doc-cell-input"


def view(chapter: Row) -> rx.Component:
    return mn.stack(
        rx.el.table(
            rx.el.thead(
                rx.el.tr(
                    rx.foreach(
                        chapter["columns"].to(list[str]),
                        lambda column: rx.el.th(column, scope="col"),
                    )
                )
            ),
            rx.el.tbody(
                rx.foreach(
                    chapter["rows"].to(list[list[str]]),
                    lambda row: rx.el.tr(
                        rx.foreach(row, rx.el.td),
                    ),
                )
            ),
            class_name="aq-doc-table",
        ),
        rx.cond(
            chapter["rows"].to(list[list[str]]).length() == 0,
            mn.text(EMPTY, fz="12px", c=theme.TEXT_MUTED),
        ),
        gap=8,
    )


def _input(value: rx.Var, on_blur: rx.EventType, key: rx.Var) -> rx.Component:
    """Uncontrolled, keyed by place and text: a save keeps the focus, while a
    different stored text or a failed save shows the stored text again."""
    return rx.el.textarea(
        default_value=value,
        on_blur=on_blur,
        read_only=ChapterState.chapter_locked,
        rows=1,
        class_name=CELL_CLASS,
        key=key,
    )


def _grid(chapter: Row) -> rx.Component:
    return rx.el.table(
        rx.el.thead(
            rx.el.tr(
                rx.foreach(
                    chapter["columns"].to(list[str]),
                    lambda column, index: rx.el.th(
                        _input(
                            column,
                            lambda text: ChapterState.rename_column(index, text),  # ty: ignore[invalid-argument-type]
                            ChapterState.input_reset.to(str)
                            + "-h-"
                            + index.to(str)
                            + "-"
                            + column,
                        ),
                        scope="col",
                        class_name="aq-doc-cell-edit",
                    ),
                ),
                rx.el.th(""),
            )
        ),
        rx.el.tbody(
            rx.foreach(
                chapter["rows"].to(list[list[str]]),
                lambda row, r: rx.el.tr(
                    rx.foreach(
                        row,
                        lambda cell, c: rx.el.td(
                            _input(
                                cell,
                                lambda text: ChapterState.set_cell(r, c, text),  # ty: ignore[invalid-argument-type]
                                ChapterState.input_reset.to(str)
                                + "-"
                                + r.to(str)
                                + "-"
                                + c.to(str)
                                + "-"
                                + cell,
                            ),
                            class_name="aq-doc-cell-edit",
                        ),
                    ),
                    rx.el.td(
                        mn.action_icon(
                            rx.icon("x", size=14),
                            variant="subtle",
                            color="gray",
                            size="sm",
                            aria_label=REMOVE_ROW,
                            disabled=ChapterState.chapter_locked,
                            on_click=ChapterState.remove_row(r),
                        ),
                        width="32px",
                    ),
                ),
            )
        ),
        class_name="aq-doc-table",
    )


def editing(chapter: Row, header: rx.Component) -> rx.Component:
    locked = ChapterState.chapter_locked
    return rx.fragment(
        floating_toolbar(
            tool_button(ADD_ROW, disabled=locked, on_click=ChapterState.add_row),
            tool_button(
                ADD_COLUMN,
                disabled=locked | ~ChapterState.can_add_column,
                on_click=ChapterState.add_column,
            ),
            toolbar_separator(),
            tool_button(
                AI_LABEL,
                disabled=locked | ChapterState.drafting,
                on_click=ChapterState.draft_active(""),
            ),
        ),
        header,
        _grid(chapter),
    )
