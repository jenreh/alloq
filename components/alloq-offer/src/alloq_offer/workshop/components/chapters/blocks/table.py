"""Table chapters: a plain grid; the table editor while selected."""

import reflex as rx
from alloq_commons import theme

import appkit_mantine as mn
from alloq_offer.workshop.components.chapters.blocks import Row, caption
from alloq_offer.workshop.components.chapters.editor import (
    table_editor,
    tool_button,
)
from alloq_offer.workshop.states.chapter_state import ChapterState

AI_LABEL = "KI-Vorschlag"
EMPTY = "Die Tabelle hat noch keine Zeilen."
EDIT_DEBOUNCE_MS = 800


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
        caption.view(chapter),
        gap=8,
    )


def editing(chapter: Row, header: rx.Component) -> rx.Component:
    """The table editor (Confluence): its toolbar floats above the table while
    the cursor is in it; cell text uses the page toolbar."""
    locked = ChapterState.chapter_locked
    key = chapter["key"].to(str)
    mount = chapter["mount"].to(str)
    return rx.fragment(
        header,
        table_editor(
            tool_button(
                AI_LABEL,
                disabled=locked | ChapterState.drafting,
                on_click=ChapterState.draft_active(""),
            ),
            content=chapter["html"].to(str),
            editable=~locked,
            on_update=lambda html: ChapterState.save_table(key, html, mount).debounce(
                EDIT_DEBOUNCE_MS
            ),
            on_blur=lambda html: ChapterState.save_table(key, html, mount),
            on_focus=ChapterState.select_chapter(key),
            on_remove=ChapterState.ask_remove,
            key=mount,
        ),
        caption.editing(chapter),
    )
