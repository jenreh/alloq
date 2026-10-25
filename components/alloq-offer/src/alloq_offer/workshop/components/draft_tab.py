"""Tab "Entwurf": start card, stage progress, summary, decisions and sources."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.workshop.components.sources_panel import sources_panel
from alloq_offer.workshop.services import draft_overview
from alloq_offer.workshop.states.draft_state import DraftState
from alloq_offer.workshop.states.export_state import ExportState
from alloq_offer.workshop.states.map_state import MapState
from alloq_offer.workshop.states.sources_state import SourcesState
from alloq_offer.workshop.states.workshop_state import (
    TAB_BRIEFING,
    TAB_CHAPTERS,
    TAB_MAP,
    WorkshopState,
)

Row = ObjectVar[dict[str, Any]]

START_TITLE = "Ersten Angebotsentwurf erzeugen"
START_TEXT = (
    "Die Werkstatt erstellt aus den ausgewählten Quellen in einem Durchlauf die "
    "Story Map, die Stories, das Briefing, alle Kapitel "
    "der Vorlage und einen Word-Entwurf. Danach entscheiden Sie nur noch, was die "
    "KI nicht festlegen darf."
)
AUTO_DRAFT_LABEL = "Automatisch entwerfen, sobald neue Quellen nutzbar sind"
LOOKS_FOR_TITLE = "Ohne Quellen bleibt die Map leer. Die KI erkennt in den Quellen:"
LOOKS_FOR = (
    "Rollen und Ziele · Auslöser und Ergebnisse · Aktivitäten und Aufgaben · "
    "Varianten, Rückfragen und Übergaben · Ist- und Soll-Zustand"
)
PROGRESS_TITLE = "Entwurf in einem Durchlauf"
SUMMARY_TITLE = "Entwurf erstellt"
SHOW_MAP = "Story Map ansehen"
SHOW_CHAPTERS = "Kapitel ansehen"
DOWNLOAD_DRAFT = "Word-Entwurf herunterladen"
DECISIONS_TITLE = "Braucht Ihre Entscheidung"
NO_DECISIONS = "Keine offenen Entscheidungen."
STAGE_COLORS = {
    draft_overview.DONE: "green",
    draft_overview.RUNNING: "blue",
    draft_overview.WAITING: "gray",
    draft_overview.FAILED: "red",
}
POLL_MS = 3000


def start_card() -> rx.Component:
    return mn.stack(
        mn.stack(
            mn.text(START_TITLE, fz="18px", fw=650),
            mn.text(START_TEXT, c=theme.TEXT_MUTED, lh="1.5", maw=640),
            gap=6,
        ),
        mn.group(
            mn.button(
                SourcesState.generate_label,
                size="md",
                radius="md",
                disabled=~SourcesState.can_generate,
                loading=SourcesState.draft_working,
                on_click=[SourcesState.generate_draft, DraftState.load_overview],
            ),
            mn.checkbox(
                label=AUTO_DRAFT_LABEL,
                checked=WorkshopState.auto_draft,
                on_change=WorkshopState.set_auto_draft,
            ),
            gap=12,
            align="center",
        ),
        rx.cond(
            SourcesState.draft_message != "",
            mn.text(SourcesState.draft_message, fz="13px", c=theme.TEXT_MUTED),
        ),
        mn.stack(
            mn.text(LOOKS_FOR_TITLE, fz="12px", fw=600, c=theme.TEXT_MUTED),
            mn.text(LOOKS_FOR, fz="13px"),
            gap=8,
            pt=6,
            style={"borderTop": f"1px solid {theme.SEPARATOR}"},
        ),
        gap=18,
        p=28,
        style=theme.CARD,
    )


def _stage(stage: Row) -> rx.Component:
    status = stage["status"].to(str)
    return mn.group(
        mn.text(stage["label"].to(str), fz="13px"),
        mn.badge(
            status,
            color=rx.match(status, *STAGE_COLORS.items(), "gray"),  # ty: ignore[invalid-argument-type]
            variant="light",
            size="sm",
        ),
        justify="space-between",
        py=6,
        style={"borderTop": f"1px solid {theme.SEPARATOR}"},
    )


def progress_card() -> rx.Component:
    return mn.stack(
        mn.text(PROGRESS_TITLE, fw=650, fz="14px"),
        mn.progress(
            value=DraftState.pipeline_progress,
            size="sm",
            radius="xl",
            striped=DraftState.working,
            animated=DraftState.working,
        ),
        mn.stack(rx.foreach(DraftState.stages, _stage), gap=0),
        rx.cond(
            SourcesState.draft_message != "",
            mn.text(SourcesState.draft_message, fz="12px", c=theme.TEXT_MUTED),
        ),
        gap=8,
        p=20,
        style=theme.CARD,
    )


def _count(item: Row) -> rx.Component:
    return mn.stack(
        mn.text(item["value"].to(str), fz="20px", fw=650),
        mn.text(item["label"].to(str), fz="12px", c=theme.TEXT_MUTED),
        gap=0,
    )


def summary_card() -> rx.Component:
    return mn.stack(
        mn.text(SUMMARY_TITLE, fz="18px", fw=650),
        mn.group(rx.foreach(DraftState.counts, _count), gap=32),
        mn.group(
            mn.button(
                SHOW_MAP,
                variant="default",
                on_click=WorkshopState.set_tab(TAB_MAP),
            ),
            mn.button(
                SHOW_CHAPTERS,
                variant="default",
                on_click=WorkshopState.set_tab(TAB_CHAPTERS),
            ),
            mn.button(
                DOWNLOAD_DRAFT,
                disabled=~DraftState.has_draft_file,
                on_click=ExportState.download_export(DraftState.draft_export_id),
            ),
            gap=10,
        ),
        gap=16,
        p=24,
        style=theme.CARD,
    )


def _decision_button(decision: Row) -> rx.Component:
    label = decision["action"].to(str)
    return rx.match(
        decision["key"].to(str),
        (
            draft_overview.TARGET_BRIEFING,
            mn.button(
                label,
                size="xs",
                variant="default",
                on_click=WorkshopState.set_tab(TAB_BRIEFING),
            ),
        ),
        mn.button(
            label,
            size="xs",
            variant="default",
            on_click=WorkshopState.set_tab(TAB_CHAPTERS),
        ),
    )


def _decision(decision: Row) -> rx.Component:
    return mn.group(
        mn.stack(
            mn.text(decision["title"].to(str), fw=600, fz="13px"),
            mn.text(decision["text"].to(str), fz="12px", c=theme.TEXT_MUTED),
            gap=2,
            style={"flex": "1", "minWidth": "0"},
        ),
        _decision_button(decision),
        wrap="nowrap",
        py=8,
        style={"borderTop": f"1px solid {theme.SEPARATOR}"},
    )


def decisions_card() -> rx.Component:
    return mn.stack(
        mn.text(DECISIONS_TITLE, fw=650, fz="14px"),
        rx.cond(
            DraftState.decisions.length() > 0,
            mn.stack(rx.foreach(DraftState.decisions, _decision), gap=0),
            mn.text(NO_DECISIONS, fz="13px", c=theme.TEXT_MUTED),
        ),
        gap=8,
        p=20,
        style=theme.CARD,
    )


def draft_tab() -> rx.Component:
    """Draft overview on the left; the sources stay in the side column."""
    return rx.box(
        rx.box(
            mn.stack(
                rx.cond(MapState.has_map, summary_card(), start_card()),
                rx.cond(DraftState.started, progress_card()),
                rx.cond(MapState.has_map, decisions_card()),
                rx.cond(
                    DraftState.working,
                    rx.moment(
                        interval=POLL_MS,
                        on_change=DraftState.load_overview,
                        display="none",
                    ),
                ),
                gap=16,
                maw=880,
            ),
            class_name="aq-split-main aq-ws-pad",
        ),
        sources_panel(),
        class_name="aq-split",
    )
