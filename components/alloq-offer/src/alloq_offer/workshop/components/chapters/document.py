"""The page: frame placeholders and one block per chapter; one block is edited."""

from collections.abc import Callable

import reflex as rx
from alloq_commons import theme

import appkit_mantine as mn
from alloq_offer.workshop.components.chapters.blocks import (
    Row,
    calc,
    prose,
    stories,
    table,
)
from alloq_offer.workshop.components.chapters.labels import (
    FRAME_NOTE,
    TYPE_LABELS,
    by_type,
)
from alloq_offer.workshop.states.chapter_state import BLOCK_ID_PREFIX, ChapterState

ADD_CHAPTER = "+ Kapitel einfügen"
DOCUMENT_LABEL = "Angebotsdokument"
BLOCKS: dict[str, tuple[Callable, Callable]] = {
    "prose": (prose.view, prose.editing),
    "table": (table.view, table.editing),
    "stories": (stories.view, stories.editing),
    "calc": (calc.view, calc.editing),
}


def _frame(title: rx.Var[str]) -> rx.Component:
    return rx.el.div(
        rx.el.h3(title, class_name="aq-doc-frame-title"),
        mn.text(FRAME_NOTE, fz="12px", c=theme.TEXT_MUTED),
        class_name="aq-doc-frame",
    )


def _header(chapter: Row, *, selectable: bool = False) -> rx.Component:
    """Number, title and type; a reading block's title is the keyboard way in."""
    text = chapter["number"].to(str) + " " + chapter["title"].to(str)
    title = (
        rx.el.button(
            text,
            type="button",
            class_name="aq-doc-title-button",
            on_click=ChapterState.select_chapter(chapter["key"].to(str)),
        )
        if selectable
        else text
    )
    return rx.el.div(
        rx.el.h2(title, class_name="aq-doc-block-title"),
        rx.el.span(by_type(chapter["type"], TYPE_LABELS), class_name="aq-doc-badge"),
        class_name="aq-doc-block-head",
    )


def _reading(chapter: Row) -> rx.Component:
    cases = [(kind, read(chapter)) for kind, (read, _) in BLOCKS.items()]
    return rx.match(chapter["type"].to(str), *cases, rx.fragment())


def _editing(chapter: Row) -> rx.Component:
    header = _header(chapter)
    cases = [(kind, edit(chapter, header)) for kind, (_, edit) in BLOCKS.items()]
    return rx.match(chapter["type"].to(str), *cases, rx.fragment())


def _block(chapter: Row) -> rx.Component:
    key = chapter["key"].to(str)
    block_id = BLOCK_ID_PREFIX + key
    level = chapter["level"].to(str)
    return rx.cond(
        ChapterState.active_key == key,
        rx.el.section(
            _editing(chapter),
            id=block_id,
            class_name="aq-doc-block",
            custom_attrs={"data-selected": "true", "data-level": level},
            on_click=rx.stop_propagation,
        ),
        rx.el.section(
            _header(chapter, selectable=True),
            _reading(chapter),
            id=block_id,
            class_name="aq-doc-block",
            custom_attrs={"data-level": level},
            on_click=ChapterState.select_chapter(key).stop_propagation,
        ),
    )


def document() -> rx.Component:
    """The page in the middle column; a click beside the blocks ends the editing."""
    return rx.box(
        rx.el.article(
            rx.foreach(ChapterState.frame_before, _frame),
            rx.foreach(ChapterState.chapters, _block),
            rx.el.button(
                ADD_CHAPTER,
                type="button",
                class_name="aq-doc-add",
                on_click=ChapterState.open_add.stop_propagation,
            ),
            rx.foreach(ChapterState.frame_after, _frame),
            class_name="aq-doc-page",
            aria_label=DOCUMENT_LABEL,
        ),
        class_name="aq-split-main aq-doc-main",
        on_click=ChapterState.clear_selection,
    )
