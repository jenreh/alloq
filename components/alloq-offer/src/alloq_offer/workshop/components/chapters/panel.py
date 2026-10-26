"""The chapter panel on the right: settings, AI proposal, findings, history."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.list_view import inspector_section
from alloq_commons.components.toolbar import segmented

import appkit_mantine as mn
from alloq_offer.workshop.components.chapters.blocks import Row
from alloq_offer.workshop.components.chapters.blocks.calc import CALC_SECTION_ID
from alloq_offer.workshop.components.chapters.labels import (
    TYPE_HINTS,
    TYPE_LABELS,
    by_type,
)
from alloq_offer.workshop.components.review_panel import calc_section, findings_section
from alloq_offer.workshop.states.chapter_panel_mixin import GROUP_OPTIONS
from alloq_offer.workshop.states.chapter_state import ChapterState
from alloq_offer.workshop.states.outline_mixin import LEVEL_OPTIONS
from alloq_offer.workshop.states.workshop_state import TAB_MAP, WorkshopState

PANEL_LABEL = "Kapitel"
TYPE_PREFIX = "Kapiteltyp · "
HEADING = "Überschrift"
LEVEL = "Ebene"
GUIDE_TITLE = "Leitfrage"
RULES_TITLE = "Regeln"
GROUP_BY = "Gruppieren nach"
STORIES_NOTE = (
    "Die Stories kommen aus der Story Map. Die Map selbst erscheint nicht im Dokument."
)
OPEN_MAP = "Story Map öffnen"
COLUMNS = "Spalten"
PROTECTED_LABEL = "Kapitel schützen"
MOVE_UP = "Nach oben"
MOVE_DOWN = "Nach unten"
REMOVE = "Entfernen"
REQUIRED_NOTE = "Pflichtkapitel bleiben im Angebot."
REMOVED_TITLE = "Entfernte Kapitel"
RESTORE = "Wiederherstellen"
NOTHING_SELECTED = "Wählen Sie ein Kapitel im Dokument aus."
PROPOSAL_TITLE = "KI-Vorschlag"
PROPOSAL_HINT = (
    "Der Vorschlag ändert das Kapitel erst, wenn Sie ihn übernehmen. "
    "Er bestätigt keine fachliche Entscheidung."
)
ACCEPT = "Vorschlag übernehmen"
REJECT = "Verwerfen"
HISTORY = "Verlauf"
HISTORY_CLOSE = "Verlauf schließen"
WORKING_LABEL = "Die KI arbeitet …"


def _diff_line(line: Row) -> rx.Component:
    kind = line["kind"].to(str)
    return mn.text(
        rx.cond(kind == "added", "+ ", rx.cond(kind == "removed", "- ", "  "))
        + line["text"].to(str),
        fz="12px",
        lh="1.5",
        c=rx.cond(
            kind == "added",
            theme.POSITIVE,
            rx.cond(kind == "removed", theme.NEGATIVE, theme.TEXT),
        ),
        style={"whiteSpace": "pre-wrap"},
    )


def _proposal() -> rx.Component:
    return inspector_section(
        PROPOSAL_TITLE,
        mn.text(PROPOSAL_HINT, fz="12px", c=theme.TEXT_MUTED, lh="1.5"),
        mn.stack(
            rx.foreach(
                ChapterState.proposal["diff"].to(list[dict[str, Any]]), _diff_line
            ),
            gap=0,
        ),
        mn.group(
            mn.button(
                ACCEPT,
                size="xs",
                disabled=ChapterState.chapter_locked,
                on_click=ChapterState.accept_proposal,
            ),
            mn.button(
                REJECT,
                variant="subtle",
                size="xs",
                on_click=ChapterState.reject_proposal,
            ),
        ),
    )


def _history_entry(entry: Row) -> rx.Component:
    return mn.stack(
        mn.group(
            mn.text(
                "Revision "
                + entry["number"].to(str)
                + " · "
                + entry["origin"].to(str)
                + " · "
                + entry["created"].to(str),
                fz="12px",
                fw=600,
            ),
            mn.button(
                RESTORE,
                variant="subtle",
                size="compact-xs",
                on_click=ChapterState.restore(entry["number"].to(int)),
            ),
            justify="space-between",
        ),
        mn.text(entry["author"].to(str), fz="11px", c=theme.TEXT_MUTED),
        rx.foreach(entry["diff"].to(list[dict[str, Any]]), _diff_line),
        gap=2,
        py=8,
        class_name="aq-doc-panel-sep",
    )


def _history() -> rx.Component:
    return rx.cond(
        ChapterState.history_open,
        inspector_section(
            HISTORY,
            mn.button(
                HISTORY_CLOSE,
                variant="subtle",
                size="compact-xs",
                on_click=ChapterState.close_history,
            ),
            mn.stack(rx.foreach(ChapterState.history, _history_entry), gap=0),
        ),
        mn.button(
            HISTORY, variant="default", size="xs", on_click=ChapterState.open_history
        ),
    )


def _head(active: Row) -> rx.Component:
    return mn.stack(
        mn.text(
            TYPE_PREFIX + by_type(active["type"], TYPE_LABELS),
            fz="11.5px",
            fw=600,
            c=theme.TEXT_MUTED,
        ),
        mn.text(
            active["number"].to(str) + " " + active["title"].to(str),
            fz="15px",
            fw=650,
        ),
        mn.text(ChapterState.status_line, fz="12px", c=theme.TEXT_MUTED),
        gap=2,
    )


def _settings(active: Row) -> rx.Component:
    return mn.stack(
        mn.text_input(
            label=HEADING,
            default_value=active["title"].to(str),
            on_blur=ChapterState.rename_active,
            disabled=ChapterState.chapter_locked,
            custom_attrs={"maxLength": 255},
            key=ChapterState.active_key
            + "-"
            + active["title"].to(str)
            + "-"
            + ChapterState.input_reset.to(str),
            size="xs",
        ),
        mn.stack(
            mn.text(LEVEL, fz="12px", fw=600),
            segmented(
                active["level"].to(str),
                ChapterState.set_active_level,
                LEVEL_OPTIONS,
                disabled=ChapterState.chapter_locked | ChapterState.is_first,
            ),
            gap=4,
        ),
        mn.text(by_type(active["type"], TYPE_HINTS), fz="12px", c=theme.TEXT_MUTED),
        gap=10,
    )


def _type_settings(active: Row) -> rx.Component:
    return rx.match(
        active["type"].to(str),
        (
            "stories",
            inspector_section(
                GROUP_BY,
                segmented(
                    active["group_by"].to(str),
                    ChapterState.set_group_by,
                    GROUP_OPTIONS,
                    disabled=ChapterState.chapter_locked,
                ),
                mn.text(STORIES_NOTE, fz="12px", c=theme.TEXT_MUTED),
                mn.anchor(
                    OPEN_MAP,
                    fz="12px",
                    fw=500,
                    on_click=WorkshopState.set_tab(TAB_MAP),
                ),
            ),
        ),
        (
            "table",
            inspector_section(
                COLUMNS,
                mn.text(
                    active["columns"].to(list[str]).join(" · "),
                    fz="12px",
                    c=theme.TEXT_MUTED,
                ),
            ),
        ),
        ("calc", rx.box(calc_section(), id=CALC_SECTION_ID)),
        rx.fragment(),
    )


def _guide(active: Row) -> rx.Component:
    return rx.fragment(
        rx.cond(
            active["guiding_question"].to(str) != "",
            inspector_section(
                GUIDE_TITLE,
                mn.text(active["guiding_question"].to(str), fz="13px", lh="1.5"),
            ),
        ),
        rx.cond(
            active["rules"].to(list[str]).length() > 0,
            inspector_section(
                RULES_TITLE,
                rx.foreach(
                    active["rules"].to(list[str]),
                    lambda rule: mn.text("· " + rule, fz="12px", c=theme.TEXT_MUTED),
                ),
            ),
        ),
    )


def _actions(active: Row) -> rx.Component:
    return mn.stack(
        mn.switch(
            label=PROTECTED_LABEL,
            checked=active["protected"].to(bool),
            on_change=ChapterState.set_protected,
        ),
        mn.group(
            mn.button(
                MOVE_UP,
                variant="default",
                size="xs",
                disabled=ChapterState.is_first | ChapterState.chapter_locked,
                on_click=ChapterState.move_active(-1),
            ),
            mn.button(
                MOVE_DOWN,
                variant="default",
                size="xs",
                disabled=ChapterState.is_last | ChapterState.chapter_locked,
                on_click=ChapterState.move_active(1),
            ),
            rx.cond(
                active["required"].to(bool),
                mn.text(REQUIRED_NOTE, fz="12px", c=theme.TEXT_MUTED),
                mn.button(
                    REMOVE,
                    variant="subtle",
                    color="red",
                    size="xs",
                    disabled=ChapterState.chapter_locked,
                    on_click=ChapterState.ask_remove,
                ),
            ),
            gap=6,
        ),
        gap=10,
        pt=12,
        class_name="aq-doc-panel-sep",
    )


def _removed() -> rx.Component:
    return rx.cond(
        ChapterState.has_removed,
        inspector_section(
            REMOVED_TITLE,
            rx.foreach(
                ChapterState.removed_chapters,
                lambda chapter: mn.group(
                    mn.text(chapter["title"], fz="12px", class_name="aq-doc-grow"),
                    mn.button(
                        RESTORE,
                        variant="subtle",
                        size="compact-xs",
                        on_click=ChapterState.restore_chapter(chapter["key"]),
                    ),
                    justify="space-between",
                    wrap="nowrap",
                ),
            ),
        ),
    )


def _selected() -> rx.Component:
    active = ChapterState.active
    return mn.stack(
        _head(active),
        _settings(active),
        _type_settings(active),
        _guide(active),
        rx.cond(ChapterState.drafting, mn.text(WORKING_LABEL, fz="12px")),
        rx.cond(ChapterState.has_proposal, _proposal()),
        findings_section(),
        _history(),
        _actions(active),
        gap=16,
    )


def panel() -> rx.Component:
    return rx.el.aside(
        rx.cond(
            ChapterState.has_active,
            _selected(),
            mn.text(NOTHING_SELECTED, fz="13px", c=theme.TEXT_MUTED),
        ),
        _removed(),
        class_name="aq-inspector aq-doc-panel",
        aria_label=PANEL_LABEL,
    )
