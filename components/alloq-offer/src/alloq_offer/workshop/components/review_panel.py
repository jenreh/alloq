"""Findings and calculation in the side column of the chapters tab."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.list_view import inspector_section
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.workshop.states.chapter_state import ChapterState
from alloq_offer.workshop.states.review_state import (
    CHAPTER_PREFIX,
    ReviewState,
)

Row = ObjectVar[dict[str, Any]]

FINDINGS_TITLE = "Befunde"
RUN_CHECKS = "Prüfen"
RUN_REVIEW = "KI-Review"
NO_FINDINGS = "Keine offenen Befunde."
GENERAL_TITLE = "Weitere Befunde"
ACCEPT = "Akzeptieren"
REOPEN = "Wieder öffnen"
CONFIRM_DECISION = "Akzeptieren bestätigen"
CANCEL = "Abbrechen"
REASON_PLACEHOLDER = "Begründung (Pflicht)"
BLOCKER_HINT = "Blockiert die finale Fassung."
ACCEPTED_LABEL = "Akzeptiert"
SEVERITY_COLORS = {"Blocker": "red", "Warnung": "yellow", "Hinweis": "gray"}
CALC_TITLE = "Kalkulation"
CONFIRM_CALC = "Kalkulation bestätigen"
CALC_CONFIRMED = "Bestätigt"
CALC_OPEN = "Nicht bestätigt"
PRICE_REQUIRED = "Preis erforderlich"
VALIDITY_LABEL = "Bindefrist"
CALC_HINT = (
    "Die Werte stammen aus dem Angebot. Ändert sich ein Wert nach der Bestätigung, "
    "wird die Bestätigung zurückgenommen."
)
POLL_MS = 3000


def _decision_form() -> rx.Component:
    return mn.stack(
        mn.text_input(
            placeholder=REASON_PLACEHOLDER,
            value=ReviewState.reason,
            on_change=ReviewState.set_reason,
            size="xs",
        ),
        mn.group(
            mn.button(
                CONFIRM_DECISION,
                size="compact-xs",
                on_click=ReviewState.accept_finding,
            ),
            mn.button(
                CANCEL,
                variant="subtle",
                size="compact-xs",
                on_click=ReviewState.cancel_decide,
            ),
            gap=6,
        ),
        gap=6,
    )


def _actions(finding: Row) -> rx.Component:
    return rx.cond(
        finding["decision"].to(str) == "akzeptiert",
        mn.stack(
            mn.text(
                ACCEPTED_LABEL
                + ": "
                + finding["reason"].to(str)
                + " ("
                + finding["decided_by"].to(str)
                + ")",
                fz="12px",
                c=theme.TEXT_MUTED,
            ),
            mn.button(
                REOPEN,
                variant="subtle",
                size="compact-xs",
                on_click=ReviewState.reopen_finding(finding["id"].to(int)),
            ),
            gap=4,
        ),
        rx.cond(
            finding["acceptable"].to(bool),
            rx.cond(
                ReviewState.deciding_id == finding["id"].to(int),
                _decision_form(),
                mn.button(
                    ACCEPT,
                    variant="default",
                    size="compact-xs",
                    on_click=ReviewState.start_decide(finding["id"].to(int)),
                ),
            ),
            mn.text(BLOCKER_HINT, fz="12px", c=theme.TEXT_MUTED),
        ),
    )


def _finding(finding: Row) -> rx.Component:
    return mn.stack(
        mn.group(
            mn.badge(
                finding["severity"].to(str),
                color=rx.match(
                    finding["severity"].to(str),
                    *SEVERITY_COLORS.items(),
                    "gray",
                ),  # ty: ignore[invalid-argument-type]
                variant="light",
                size="xs",
            ),
            rx.cond(
                finding["source"].to(str) == "KI",
                mn.badge("KI", color="blue", variant="outline", size="xs"),
            ),
            gap=6,
        ),
        mn.text(finding["message"].to(str), fz="13px", lh="1.45"),
        _actions(finding),
        gap=6,
        py=8,
        style={"borderTop": f"1px solid {theme.SEPARATOR}"},
    )


def _for_active(finding: Row) -> rx.Component:
    return rx.cond(
        finding["target"].to(str) == CHAPTER_PREFIX + ChapterState.active_key,
        _finding(finding),
    )


def findings_section() -> rx.Component:
    return inspector_section(
        FINDINGS_TITLE,
        mn.group(
            mn.button(
                RUN_CHECKS,
                variant="default",
                size="xs",
                on_click=ReviewState.run_checks,
            ),
            mn.button(
                RUN_REVIEW,
                variant="default",
                size="xs",
                loading=ReviewState.reviewing,
                on_click=ReviewState.request_ai_review,
            ),
            gap=6,
        ),
        mn.text(
            ReviewState.blocker_count.to(str) + " blockierend",
            fz="12px",
            c=theme.TEXT_MUTED,
        ),
        mn.stack(rx.foreach(ReviewState.findings, _for_active), gap=0),
        rx.cond(
            ReviewState.general_findings.length() > 0,
            mn.stack(
                mn.text(GENERAL_TITLE, fz="12px", fw=600, c=theme.TEXT_MUTED, pt=8),
                mn.stack(rx.foreach(ReviewState.general_findings, _finding), gap=0),
                gap=0,
            ),
        ),
        rx.cond(
            ReviewState.reviewing,
            rx.moment(
                interval=POLL_MS,
                on_change=ReviewState.refresh_review,
                display="none",
            ),
        ),
    )


def _calc_row(row: Row) -> rx.Component:
    return mn.group(
        mn.text(row["label"].to(str), fz="12.5px", c=theme.TEXT_MUTED),
        mn.text(row["value"].to(str), fz="13px", fw=600),
        justify="space-between",
    )


def calc_section() -> rx.Component:
    return inspector_section(
        CALC_TITLE,
        mn.stack(rx.foreach(ReviewState.calc_rows, _calc_row), gap=4),
        rx.cond(
            ReviewState.calc_confirmed,
            mn.text(
                CALC_CONFIRMED
                + ": "
                + ReviewState.calc_confirmed_by
                + ", "
                + ReviewState.calc_confirmed_at,
                fz="12px",
                c=theme.POSITIVE,
            ),
            mn.text(CALC_OPEN, fz="12px", c=theme.WARNING),
        ),
        mn.button(
            CONFIRM_CALC,
            size="xs",
            variant=rx.cond(ReviewState.calc_confirmed, "default", "filled"),
            on_click=ReviewState.confirm_calculation,
        ),
        mn.switch(
            label=PRICE_REQUIRED,
            checked=ReviewState.price_required,
            on_change=ReviewState.set_price_required,
        ),
        mn.date_input(
            label=VALIDITY_LABEL,
            value=ReviewState.validity_date,
            on_change=ReviewState.set_validity,
            clearable=True,
            locale="de",
            value_format="DD.MM.YYYY",
            size="xs",
        ),
        mn.text(CALC_HINT, fz="12px", c=theme.TEXT_MUTED, lh="1.5"),
    )
