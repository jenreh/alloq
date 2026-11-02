"""Text chapters: every one is edited in place; the AI menu joins the toolbar."""

import reflex as rx
from alloq_commons import theme

import appkit_mantine as mn
from alloq_offer.workshop.components.chapters.blocks import Row
from alloq_offer.workshop.components.chapters.editor import (
    PROSE_CLASS,
    chapter_editor,
    tool_button,
    toolbar_separator,
)
from alloq_offer.workshop.states.chapter_state import (
    SHORTEN,
    TECHNICAL,
    UNSUPPORTED_NOTE,
    ChapterState,
)

AI_MENU = "KI"
SHORTEN_LABEL = "Kürzen"
TECHNICAL_LABEL = "Technischer"
OWN_LABEL = "Eigene Anweisung …"
EDIT_DEBOUNCE_MS = 800


def view(chapter: Row) -> rx.Component:
    return rx.html(chapter["html"].to(str), class_name=PROSE_CLASS)


def _ai_tools() -> list[rx.Component]:
    """The AI actions of a text chapter, in one menu so the card stays one row."""
    return [
        toolbar_separator(),
        mn.menu(
            mn.menu.target(
                tool_button(
                    AI_MENU,
                    left_section=rx.icon("sparkles", size=14),
                    disabled=ChapterState.chapter_locked | ChapterState.drafting,
                    loading=ChapterState.drafting,
                )
            ),
            mn.menu.dropdown(
                mn.menu.item(
                    SHORTEN_LABEL, on_click=ChapterState.draft_active(SHORTEN)
                ),
                mn.menu.item(
                    TECHNICAL_LABEL, on_click=ChapterState.draft_active(TECHNICAL)
                ),
                mn.menu.item(OWN_LABEL, on_click=ChapterState.open_instruction),
            ),
            position="bottom-end",
            shadow="md",
            z_index=theme.PAGE_POPOVER_Z_INDEX,
        ),
    ]


def ai_menu() -> rx.Component:
    """The AI actions for the selected text chapter, at the end of the toolbar."""
    return rx.el.div(*_ai_tools(), class_name="aq-doc-ai-tools")


def block(chapter: Row, header: rx.Component) -> rx.Component:
    """The chapter text, editable in place; content the editor cannot hold stays
    read-only with a note."""
    key = chapter["key"].to(str)
    mount = chapter["mount"].to(str)
    return rx.cond(
        chapter["can_edit"].to(bool),
        chapter_editor(
            content=chapter["html"].to(str),
            editable=~chapter["protected"].to(bool),
            on_update=lambda html: ChapterState.autosave(key, html, mount).debounce(
                EDIT_DEBOUNCE_MS
            ),
            on_blur=lambda html: ChapterState.autosave(key, html, mount),
            on_focus=ChapterState.select_chapter(key),
            header=header,
            # A new mount (revision saved elsewhere) starts a fresh editor.
            key=mount,
        ),
        rx.fragment(
            header,
            mn.text(UNSUPPORTED_NOTE, fz="12px", c=theme.TEXT_MUTED),
            view(chapter),
        ),
    )
