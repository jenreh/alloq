"""Value chapters: bound values of the calculation; numbers are never typed here."""

from typing import Any

import reflex as rx
from alloq_commons import theme

import appkit_mantine as mn
from alloq_offer.workshop.components.chapters.blocks import Row
from alloq_offer.workshop.components.chapters.editor import (
    floating_toolbar,
    tool_button,
)
from alloq_offer.workshop.states.chapter_state import ChapterState

ADD_VALUE = "Wert hinzufügen"
TO_CALCULATION = "Zur Kalkulation"
REMOVE_VALUE = "Wert entfernen"
CALC_SECTION_ID = "aq-calc"


def _value(value: Any) -> rx.Component:
    return rx.el.span(value["value"].to(str), class_name="aq-doc-bound")


def view(chapter: Row) -> rx.Component:
    intro = chapter["intro"].to(str)
    return mn.stack(
        rx.cond(intro != "", rx.el.p(intro, class_name="aq-doc-intro")),
        rx.el.table(
            rx.el.tbody(
                rx.foreach(
                    chapter["values"].to(list[dict[str, Any]]),
                    lambda value: rx.el.tr(
                        rx.el.th(value["label"].to(str), scope="row"),
                        rx.el.td(_value(value)),
                    ),
                )
            ),
            class_name="aq-doc-table",
        ),
        gap=10,
    )


def _grid(chapter: Row) -> rx.Component:
    return rx.el.table(
        rx.el.tbody(
            rx.foreach(
                chapter["values"].to(list[dict[str, Any]]),
                lambda value, index: rx.el.tr(
                    rx.el.th(value["label"].to(str), scope="row"),
                    rx.el.td(_value(value)),
                    rx.el.td(
                        mn.action_icon(
                            rx.icon("x", size=14),
                            variant="subtle",
                            color="gray",
                            size="sm",
                            aria_label=REMOVE_VALUE,
                            disabled=ChapterState.chapter_locked,
                            on_click=ChapterState.remove_value(index),
                        ),
                        width="32px",
                    ),
                ),
            )
        ),
        class_name="aq-doc-table",
    )


def editing(chapter: Row, header: rx.Component) -> rx.Component:
    intro = chapter["intro"].to(str)
    return rx.fragment(
        floating_toolbar(
            mn.select(
                data=ChapterState.free_fields,
                value="",
                placeholder=ADD_VALUE,
                on_change=ChapterState.add_value,
                disabled=ChapterState.chapter_locked
                | (ChapterState.free_fields.length() == 0),
                size="xs",
                w=200,
                combobox_props={"zIndex": theme.PAGE_POPOVER_Z_INDEX},
            ),
            tool_button(TO_CALCULATION, on_click=rx.scroll_to(CALC_SECTION_ID)),
        ),
        header,
        rx.cond(intro != "", rx.el.p(intro, class_name="aq-doc-intro")),
        _grid(chapter),
    )
