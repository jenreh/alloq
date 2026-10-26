"""Text chapters: the HTML of the stored text, or the editor when selected."""

import reflex as rx
from alloq_commons import theme

import appkit_mantine as mn
from alloq_offer.workshop.components.chapters.blocks import Row
from alloq_offer.workshop.components.chapters.editor import (
    PROSE_CLASS,
    chapter_editor,
    floating_toolbar,
    tool_button,
    toolbar_separator,
)
from alloq_offer.workshop.states.chapter_state import (
    SHORTEN,
    TECHNICAL,
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


def editing(chapter: Row, header: rx.Component) -> rx.Component:
    """The editor with the same typography; content the editor cannot hold stays
    read-only with a note."""
    return rx.cond(
        ChapterState.editable,
        chapter_editor(
            *_ai_tools(),
            content=ChapterState.editor_html,
            editable=~ChapterState.chapter_locked,
            on_update=lambda html: ChapterState.autosave(  # ty: ignore[invalid-argument-type]
                ChapterState.active_key, html
            ).debounce(EDIT_DEBOUNCE_MS),
            on_blur=lambda html: ChapterState.autosave(  # ty: ignore[invalid-argument-type]
                ChapterState.active_key, html
            ),
            key=ChapterState.editor_key,
            header=header,
        ),
        rx.fragment(
            floating_toolbar(*_ai_tools()[1:]),
            header,
            mn.text(ChapterState.note, fz="12px", c=theme.TEXT_MUTED),
            view(chapter),
        ),
    )
