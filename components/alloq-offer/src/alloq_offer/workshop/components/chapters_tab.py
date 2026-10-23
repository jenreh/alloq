"""Tab "Kapitel": chapter list, editor, history and proposals."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.list_view import empty_list, inspector, inspector_section
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.workshop.components.review_panel import calc_section, findings_section
from alloq_offer.workshop.states.chapter_state import (
    SHORTEN,
    TECHNICAL,
    ChapterState,
)
from alloq_offer.workshop.states.review_state import ReviewState

Row = ObjectVar[dict[str, Any]]

LIST_TITLE = "Kapitel"
DRAFT_ALL = "Fehlende Kapitel vorschlagen"
NEEDS_REVIEW = "Bitte prüfen"
BLOCKED = "Blocker"
FINDINGS = "Befunde"
PROPOSAL_BADGE = "Vorschlag"
PROTECTED_LABEL = "Kapitel schützen"
PROTECTED_BADGE = "Geschützt"
HISTORY = "Verlauf"
HISTORY_CLOSE = "Verlauf schließen"
RESTORE = "Wiederherstellen"
ACCEPT = "Vorschlag übernehmen"
REJECT = "Verwerfen"
PROPOSAL_TITLE = "KI-Vorschlag"
PROPOSAL_HINT = (
    "Der Vorschlag ändert das Kapitel erst, wenn Sie ihn übernehmen. "
    "Er bestätigt keine fachliche Entscheidung."
)
AI_TITLE = "KI-Hilfe für dieses Kapitel"
SHORTEN_LABEL = "Kürzen"
TECHNICAL_LABEL = "Technischer formulieren"
FREE_PLACEHOLDER = "Eigene Anweisung, z. B. „Nenne die Annahmen zuerst“"
FREE_LABEL = "Vorschlag anfordern"
GUIDE_TITLE = "Leitfrage"
RULES_TITLE = "Regeln der Vorlage"
WORKING_LABEL = "Die KI arbeitet …"
POLL_MS = 3000
EMPTY = "Die Kapitel entstehen, sobald das Angebot geöffnet ist."
DIFF_COLORS = {"added": theme.POSITIVE, "removed": theme.NEGATIVE}


def _list_row(chapter: Row) -> rx.Component:
    active = ChapterState.active_key == chapter["key"].to(str)
    return mn.group(
        mn.text(
            chapter["title"].to(str),
            fz="13px",
            fw=rx.cond(active, 650, 450),
            style={"flex": "1 1 auto", "minWidth": "0"},
        ),
        rx.cond(
            ReviewState.blocker_keys.contains(chapter["key"].to(str)),
            mn.badge(BLOCKED, color="red", variant="light", size="xs"),
            rx.cond(
                ReviewState.other_keys.contains(chapter["key"].to(str)),
                mn.badge(FINDINGS, color="yellow", variant="light", size="xs"),
            ),
        ),
        rx.cond(
            chapter["needs_review"].to(bool),
            mn.badge(NEEDS_REVIEW, color="yellow", variant="light", size="xs"),
        ),
        rx.cond(
            chapter["proposal"].to(bool),
            mn.badge(PROPOSAL_BADGE, color="blue", variant="light", size="xs"),
        ),
        rx.cond(
            chapter["protected"].to(bool),
            mn.badge(PROTECTED_BADGE, color="gray", variant="outline", size="xs"),
        ),
        gap=6,
        wrap="nowrap",
        px=10,
        py=8,
        on_click=ChapterState.select_chapter(chapter["key"].to(str)),
        style={
            "cursor": "pointer",
            "borderRadius": "8px",
            "background": rx.cond(active, theme.ACCENT_SOFT, "transparent"),
            "paddingLeft": rx.cond(chapter["level"].to(int) > 1, "22px", "10px"),
        },
    )


def _chapter_list() -> rx.Component:
    return mn.stack(
        mn.text(LIST_TITLE, fz="12px", fw=600, c=theme.TEXT_MUTED),
        mn.stack(rx.foreach(ChapterState.chapters, _list_row), gap=2),
        mn.button(
            DRAFT_ALL,
            variant="default",
            size="xs",
            loading=ChapterState.drafting,
            on_click=ChapterState.draft_all,
        ),
        gap=10,
        p=14,
        style={**theme.CARD, "flex": "0 0 250px"},
    )


def _editor() -> rx.Component:
    return mn.box(
        mn.rich_text_editor(
            content=ChapterState.editor_html,
            editable=~ChapterState.chapter_locked,
            on_update=lambda html: ChapterState.autosave(  # ty: ignore[invalid-argument-type]
                ChapterState.active_key, html
            ).debounce(800),
            key=ChapterState.editor_key,
            control_groups=[
                ["bold", "italic"],
                ["h3", "h4"],
                ["bulletList", "orderedList"],
                ["undo", "redo"],
            ],
            styles={"content": {"minHeight": "360px"}},
        ),
    )


def _read_only() -> rx.Component:
    return mn.stack(
        mn.text(ChapterState.note, fz="12px", c=theme.TEXT_MUTED),
        rx.foreach(
            ChapterState.preview_lines,
            lambda line: mn.text(line, fz="13px", lh="1.5"),
        ),
        gap=6,
    )


def _center() -> rx.Component:
    active = ChapterState.active
    return mn.stack(
        mn.group(
            mn.stack(
                mn.text(active["title"].to(str), fz="18px", fw=650),
                mn.text(ChapterState.status_line, fz="12px", c=theme.TEXT_MUTED),
                gap=2,
            ),
            mn.switch(
                label=PROTECTED_LABEL,
                checked=active["protected"].to(bool),
                on_change=ChapterState.set_protected,
            ),
            justify="space-between",
            align="flex-start",
        ),
        rx.cond(
            active["needs_review"].to(bool),
            mn.text(
                active["review_reason"].to(str),
                fz="12px",
                c=theme.WARNING,
            ),
        ),
        rx.cond(ChapterState.editable, _editor(), _read_only()),
        gap=12,
        p=18,
        style={**theme.CARD, "flex": "999 1 460px", "minWidth": "0"},
    )


def _diff_line(line: Row) -> rx.Component:
    return mn.text(
        rx.cond(
            line["kind"].to(str) == "added",
            "+ ",
            rx.cond(line["kind"].to(str) == "removed", "- ", "  "),
        )
        + line["text"].to(str),
        fz="12px",
        lh="1.5",
        c=rx.cond(
            line["kind"].to(str) == "added",
            theme.POSITIVE,
            rx.cond(line["kind"].to(str) == "removed", theme.NEGATIVE, theme.TEXT),
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


def _ai_help() -> rx.Component:
    return inspector_section(
        AI_TITLE,
        mn.group(
            mn.button(
                SHORTEN_LABEL,
                variant="default",
                size="xs",
                disabled=ChapterState.chapter_locked | ~ChapterState.editable,
                on_click=ChapterState.draft_active(SHORTEN),
            ),
            mn.button(
                TECHNICAL_LABEL,
                variant="default",
                size="xs",
                disabled=ChapterState.chapter_locked | ~ChapterState.editable,
                on_click=ChapterState.draft_active(TECHNICAL),
            ),
            gap=6,
        ),
        mn.textarea(
            placeholder=FREE_PLACEHOLDER,
            value=ChapterState.instruction,
            on_change=ChapterState.set_instruction,
            autosize=True,
            min_rows=2,
        ),
        mn.button(
            FREE_LABEL,
            variant="default",
            size="xs",
            loading=ChapterState.drafting,
            disabled=ChapterState.chapter_locked | ~ChapterState.editable,
            on_click=ChapterState.draft_active(""),
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
        style={"borderTop": f"1px solid {theme.SEPARATOR}"},
    )


def _context() -> rx.Component:
    active = ChapterState.active
    return mn.stack(
        inspector_section(
            GUIDE_TITLE,
            mn.text(active["guiding_question"].to(str), fz="13px", lh="1.5"),
        ),
        inspector_section(
            RULES_TITLE,
            rx.foreach(
                active["rules"].to(list[str]),
                lambda rule: mn.text("· " + rule, fz="12px", c=theme.TEXT_MUTED),
            ),
        ),
        rx.cond(ChapterState.has_proposal, _proposal()),
        rx.cond(ChapterState.active["type"].to(str) == "calc", calc_section()),
        findings_section(),
        _ai_help(),
        rx.cond(
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
                HISTORY,
                variant="default",
                size="xs",
                on_click=ChapterState.open_history,
            ),
        ),
        gap=16,
    )


def chapters_tab() -> rx.Component:
    return mn.box(
        rx.cond(
            ChapterState.has_active,
            mn.group(
                _chapter_list(),
                _center(),
                inspector(_context(), label=LIST_TITLE),
                align="flex-start",
                wrap="wrap",
                gap=16,
            ),
            empty_list(EMPTY),
        ),
        rx.cond(
            ChapterState.drafting,
            rx.moment(
                interval=POLL_MS,
                on_change=ChapterState.refresh_drafts,
                display="none",
            ),
        ),
        p=20,
    )
