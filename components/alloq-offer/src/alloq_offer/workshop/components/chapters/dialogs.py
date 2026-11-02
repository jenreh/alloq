"""Dialogs of the Kapitel tab: "+ Kapitel" and the removal confirmation."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.modal_layout import MODAL_CLASS, MODAL_OVERLAY
from alloq_commons.components.toolbar import segmented

import appkit_mantine as mn
from alloq_offer.workshop.components.chapters.labels import (
    TYPE_OPTIONS,
    TYPE_SHORT,
    by_type,
)
from alloq_offer.workshop.states.chapter_state import ChapterState
from alloq_offer.workshop.states.outline_mixin import ADD_TABS, TAB_LIBRARY

ADD_TITLE = "Kapitel einfügen"
ADD_HINT = "Das neue Kapitel kommt hinter das ausgewählte Kapitel."
LIBRARY_EMPTY = "Alle aktiven Bausteine sind schon im Angebot."
BLANK_TITLE = "Überschrift"
BLANK_TYPE = "Kapiteltyp"
INSERT = "Einfügen"
CANCEL = "Abbrechen"
REMOVE_TITLE = "Kapitel entfernen?"
REMOVE_TEXT = (
    "Das Kapitel verschwindet aus dem Dokument. Text, Verlauf und Befunde bleiben "
    "erhalten; unter „Entfernte Kapitel“ holen Sie es zurück."
)
REMOVE = "Entfernen"
INSTRUCTION_TITLE = "Eigene Anweisung an die KI"
INSTRUCTION_PLACEHOLDER = "z. B. „Nenne die Annahmen zuerst“"
INSTRUCTION_SUBMIT = "Vorschlag anfordern"
INSTRUCTION_HINT = (
    "Die KI macht einen Vorschlag. Er ändert das Kapitel erst, wenn Sie ihn übernehmen."
)


def _dialog(
    title: str, opened: rx.Var[bool], on_close: Any, *children: rx.Component
) -> rx.Component:
    """A modal in the shared padding; the header X closes it."""
    return mn.modal(
        rx.flex(
            rx.box(mn.stack(*children, gap=14, pb=18), class_name="alloq-modal-scroll"),
            direction="column",
            class_name="alloq-modal-inner",
        ),
        title=title,
        opened=opened,
        on_close=on_close,
        size="lg",
        centered=True,
        class_name=MODAL_CLASS,
        overlay_props=MODAL_OVERLAY,
    )


def _buttons(cancel: Any, submit: rx.Component) -> rx.Component:
    return mn.group(
        mn.button(CANCEL, variant="subtle", on_click=cancel),
        submit,
        justify="flex-end",
    )


def _block(block: Any) -> rx.Component:
    return rx.el.button(
        mn.group(
            mn.text(block["title"], fw=650, fz="13px", class_name="aq-doc-grow"),
            rx.el.span(by_type(block["type"], TYPE_SHORT), class_name="aq-doc-type"),
            wrap="nowrap",
        ),
        mn.text(block["description"], fz="12px", c=theme.TEXT_MUTED, lh="1.4"),
        type="button",
        class_name="aq-doc-library-item",
        on_click=ChapterState.add_block(block["key"]),
    )


def _library() -> rx.Component:
    return rx.cond(
        ChapterState.library.length() > 0,
        rx.el.div(
            rx.foreach(ChapterState.library, _block),
            class_name="aq-doc-library",
        ),
        mn.text(LIBRARY_EMPTY, fz="13px", c=theme.TEXT_MUTED, py=12),
    )


def _blank() -> rx.Component:
    return mn.stack(
        mn.text_input(
            label=BLANK_TITLE,
            value=ChapterState.blank_title,
            on_change=ChapterState.set_blank_title,
            custom_attrs={"maxLength": 255},
            data_autofocus=True,
        ),
        mn.stack(
            mn.text(BLANK_TYPE, fz="13px", fw=500),
            segmented(
                ChapterState.blank_type, ChapterState.set_blank_type, TYPE_OPTIONS
            ),
            gap=4,
        ),
        _buttons(
            ChapterState.close_add,
            mn.button(
                INSERT,
                disabled=ChapterState.blank_title.strip() == "",
                on_click=ChapterState.add_blank,
            ),
        ),
        gap=12,
    )


def add_dialog() -> rx.Component:
    return _dialog(
        ADD_TITLE,
        ChapterState.add_open,
        ChapterState.close_add,
        mn.text(ADD_HINT, fz="13px", c=theme.TEXT_MUTED),
        segmented(ChapterState.add_tab, ChapterState.set_add_tab, ADD_TABS),
        rx.cond(ChapterState.add_tab == TAB_LIBRARY, _library(), _blank()),
    )


def remove_dialog() -> rx.Component:
    return _dialog(
        REMOVE_TITLE,
        ChapterState.remove_open,
        ChapterState.cancel_remove,
        mn.text(REMOVE_TEXT, fz="13px", lh="1.5"),
        _buttons(
            ChapterState.cancel_remove,
            mn.button(REMOVE, color="red", on_click=ChapterState.remove_active),
        ),
    )


def instruction_dialog() -> rx.Component:
    return _dialog(
        INSTRUCTION_TITLE,
        ChapterState.instruction_open,
        ChapterState.close_instruction,
        mn.text(INSTRUCTION_HINT, fz="13px", c=theme.TEXT_MUTED),
        mn.textarea(
            placeholder=INSTRUCTION_PLACEHOLDER,
            value=ChapterState.instruction,
            on_change=ChapterState.set_instruction,
            autosize=True,
            min_rows=3,
            custom_attrs={"maxLength": 2000},
            data_autofocus=True,
        ),
        _buttons(
            ChapterState.close_instruction,
            mn.button(
                INSTRUCTION_SUBMIT,
                disabled=ChapterState.instruction.strip() == "",
                on_click=ChapterState.draft_active(ChapterState.instruction),
            ),
        ),
    )
