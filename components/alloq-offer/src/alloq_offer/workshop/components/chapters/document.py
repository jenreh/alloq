"""The page: one formatting toolbar, frame placeholders and one block per chapter.

Text chapters are edited in place, one after the other; the other chapter types
show their module editor when selected.
"""

from collections.abc import Callable

import reflex as rx
from alloq_commons import theme

import appkit_mantine as mn
from alloq_offer.workshop.components.chapters.blocks import (
    Row,
    calc,
    image,
    prose,
    stories,
    table,
)
from alloq_offer.workshop.components.chapters.editor import chapter_toolbar
from alloq_offer.workshop.components.chapters.insert_menu import insert_gap
from alloq_offer.workshop.components.chapters.labels import (
    FRAME_NOTE,
    TYPE_LABELS,
    by_type,
)
from alloq_offer.workshop.states.chapter_state import BLOCK_ID_PREFIX, ChapterState

ADD_CHAPTER = "+ Kapitel einfügen"
DOCUMENT_LABEL = "Angebotsdokument"
TITLE_LABEL = "Überschrift des Kapitels"
# Module chapters: read-only view, and the editor while selected.
BLOCKS: dict[str, tuple[Callable, Callable]] = {
    "table": (table.view, table.editing),
    "stories": (stories.view, stories.editing),
    "calc": (calc.view, calc.editing),
    "image": (image.view, image.editing),
}
# Hang under the chapter before them: no heading of their own.
ATTACHED = ("table", "image")


def _frame(title: rx.Var[str]) -> rx.Component:
    return rx.el.div(
        rx.el.h3(title, class_name="aq-doc-frame-title"),
        mn.text(FRAME_NOTE, fz="12px", c=theme.TEXT_MUTED),
        class_name="aq-doc-frame",
    )


def _badge(chapter: Row) -> rx.Component:
    return rx.el.span(by_type(chapter["type"], TYPE_LABELS), class_name="aq-doc-badge")


def _badge_row(chapter: Row) -> rx.Component:
    """Table and image chapters show only their type, at the right."""
    return rx.el.div(_badge(chapter), class_name="aq-doc-block-head aq-doc-attached")


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
        _badge(chapter),
        class_name="aq-doc-block-head",
    )


def _title_field(chapter: Row) -> rx.Component:
    """The heading of a text chapter, edited in place like the text below it."""
    key = chapter["key"].to(str)
    title = chapter["title"].to(str)
    return rx.el.div(
        rx.el.h2(
            rx.el.span(chapter["number"].to(str), class_name="aq-doc-number"),
            rx.el.input(
                default_value=title,
                key=key + ":" + title + ":" + ChapterState.input_reset.to_string(),
                class_name="aq-doc-title-input",
                aria_label=TITLE_LABEL,
                read_only=chapter["protected"].to(bool),
                custom_attrs={"maxLength": 255},
                on_focus=ChapterState.select_chapter(key),
                on_blur=lambda value: ChapterState.rename_chapter(key, value),
            ),
            class_name="aq-doc-block-title",
        ),
        _badge(chapter),
        class_name="aq-doc-block-head",
    )


def _reading(chapter: Row) -> rx.Component:
    cases = [(kind, read(chapter)) for kind, (read, _) in BLOCKS.items()]
    return rx.match(chapter["type"].to(str), *cases, rx.fragment())


def _attached(chapter: Row) -> rx.Var[bool]:
    return rx.Var.create(list(ATTACHED)).contains(chapter["type"].to(str))


def _editing(chapter: Row) -> rx.Component:
    header = rx.cond(_attached(chapter), _badge_row(chapter), _header(chapter))
    cases = [(kind, edit(chapter, header)) for kind, (_, edit) in BLOCKS.items()]
    return rx.match(chapter["type"].to(str), *cases, rx.fragment())


def _module_block(chapter: Row) -> rx.Component:
    key = chapter["key"].to(str)
    block_id = BLOCK_ID_PREFIX + key
    level = chapter["level"].to(str)
    return rx.cond(
        ChapterState.active_key == key,
        rx.el.section(
            _editing(chapter),
            id=block_id,
            class_name="aq-doc-block",
            custom_attrs={
                "data-selected": "true",
                "data-level": level,
                "data-type": chapter["type"].to(str),
            },
            on_click=rx.stop_propagation,
        ),
        rx.el.section(
            rx.cond(
                _attached(chapter),
                _badge_row(chapter),
                _header(chapter, selectable=True),
            ),
            _reading(chapter),
            id=block_id,
            class_name="aq-doc-block",
            custom_attrs={"data-level": level, "data-type": chapter["type"].to(str)},
            tab_index=0,
            on_click=ChapterState.select_chapter(key).stop_propagation,
        ),
    )


def _text_block(chapter: Row) -> rx.Component:
    """Always the same element, so the editor keeps its cursor on selection."""
    key = chapter["key"].to(str)
    return rx.el.section(
        prose.block(chapter, _title_field(chapter)),
        id=BLOCK_ID_PREFIX + key,
        class_name="aq-doc-block aq-doc-text-block",
        custom_attrs={
            "data-selected": rx.cond(ChapterState.active_key == key, "true", "false"),
            "data-level": chapter["level"].to(str),
        },
        on_click=rx.stop_propagation,
    )


def _block(chapter: Row) -> rx.Component:
    return rx.match(
        chapter["type"].to(str),
        ("prose", _text_block(chapter)),
        _module_block(chapter),
    )


def document() -> rx.Component:
    """The page in the middle column; a click beside the blocks ends the editing."""
    return rx.box(
        chapter_toolbar(prose.ai_menu()),
        rx.el.article(
            rx.foreach(ChapterState.frame_before, _frame),
            insert_gap(""),
            rx.foreach(
                ChapterState.chapters,
                lambda chapter: rx.fragment(
                    _block(chapter), insert_gap(chapter["key"].to(str))
                ),
            ),
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
