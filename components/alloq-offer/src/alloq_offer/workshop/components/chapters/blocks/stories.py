"""User story chapters: the written stories of the map, grouped; never typed in."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.toolbar import segmented

import appkit_mantine as mn
from alloq_offer.workshop.components.chapters.blocks import Row
from alloq_offer.workshop.components.chapters.editor import (
    floating_toolbar,
    tool_button,
)
from alloq_offer.workshop.states.chapter_panel_mixin import GROUP_OPTIONS
from alloq_offer.workshop.states.chapter_state import ChapterState
from alloq_offer.workshop.states.workshop_state import TAB_MAP, WorkshopState

SOURCE_ACTIVITY = "Aus der Story Map · gruppiert nach Aktivität"
SOURCE_SLICE = "Aus der Story Map · gruppiert nach Umsetzungsschnitt"
NO_STORIES = "Die Story Map enthält noch keine Stories."
OPEN_MAP = "Story Map öffnen"


def _story(story: Any) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            rx.el.span(story["key"].to(str), class_name="aq-doc-story-key"),
            rx.el.b(story["title"].to(str)),
            class_name="aq-doc-story-head",
        ),
        rx.el.span(story["sentence"].to(str)),
        class_name="aq-doc-story",
    )


def _group(group: Any) -> rx.Component:
    return mn.stack(
        rx.el.h3(group["title"].to(str), class_name="aq-doc-group-title"),
        rx.foreach(group["stories"].to(list[dict[str, Any]]), _story),
        gap=8,
    )


COLUMNS_LABEL = "Spalten"
SLICES_LABEL = "Umsetzungsschnitte"
ALL = "Alle"


def view(chapter: Row) -> rx.Component:
    groups = chapter["groups"].to(list[dict[str, Any]])
    source = rx.cond(
        chapter["group_by"].to(str) == "slice", SOURCE_SLICE, SOURCE_ACTIVITY
    )
    shown = chapter["filter"].to(str)
    return mn.stack(
        mn.text(
            rx.cond(shown != "", source + " · " + shown, source),
            fz="12px",
            c=theme.TEXT_MUTED,
        ),
        rx.foreach(groups, _group),
        rx.cond(groups.length() == 0, mn.text(NO_STORIES, c=theme.TEXT_MUTED)),
        gap=14,
    )


def editing(chapter: Row, header: rx.Component) -> rx.Component:
    return rx.fragment(
        floating_toolbar(
            segmented(
                chapter["group_by"].to(str),
                ChapterState.set_group_by,
                GROUP_OPTIONS,
                disabled=ChapterState.chapter_locked,
            ),
            tool_button(OPEN_MAP, on_click=WorkshopState.set_tab(TAB_MAP)),
        ),
        header,
        view(chapter),
    )


def filters(chapter: Row, **props: Any) -> list[rx.Component]:
    """Column and slice filters; nothing chosen means all stories."""
    options = ChapterState.story_options
    return [
        mn.multi_select(
            label=COLUMNS_LABEL,
            placeholder=ALL,
            data=options["activities"].to(list[dict[str, str]]),
            value=chapter["activity_ids"].to(list[str]),
            on_change=ChapterState.set_story_activities,
            disabled=ChapterState.chapter_locked,
            clearable=True,
            **props,
        ),
        mn.multi_select(
            label=SLICES_LABEL,
            placeholder=ALL,
            data=options["slices"].to(list[dict[str, str]]),
            value=chapter["slice_ids"].to(list[str]),
            on_change=ChapterState.set_story_slices,
            disabled=ChapterState.chapter_locked,
            clearable=True,
            **props,
        ),
    ]
