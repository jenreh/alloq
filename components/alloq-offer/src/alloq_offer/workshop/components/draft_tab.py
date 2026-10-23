"""Tab "Entwurf & Story Map": start card and the sources panel."""

import reflex as rx
from alloq_commons import theme

import appkit_mantine as mn
from alloq_offer.workshop.components.sources_panel import sources_panel
from alloq_offer.workshop.states.sources_state import SourcesState
from alloq_offer.workshop.states.workshop_state import WorkshopState

START_TITLE = "Ersten Angebotsentwurf erzeugen"
START_TEXT = (
    "Die Werkstatt erstellt aus den ausgewählten Quellen in einem Durchlauf die "
    "Story Map, die Stories, das Briefing, einen Umfangsvorschlag, alle Kapitel "
    "der Vorlage und einen Word-Entwurf. Danach entscheiden Sie nur noch, was die "
    "KI nicht festlegen darf."
)
AUTO_DRAFT_LABEL = "Automatisch entwerfen, sobald neue Quellen nutzbar sind"
LOOKS_FOR_TITLE = "Ohne Quellen bleibt die Map leer. Die KI erkennt in den Quellen:"
LOOKS_FOR = (
    "Rollen und Ziele · Auslöser und Ergebnisse · Aktivitäten und Aufgaben · "
    "Varianten, Rückfragen und Übergaben · Ist- und Soll-Zustand"
)


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
                on_click=SourcesState.generate_draft,
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


def draft_tab() -> rx.Component:
    return mn.group(
        mn.box(start_card(), style={"flex": "999 1 640px", "minWidth": "0"}),
        sources_panel(),
        align="flex-start",
        wrap="wrap",
        gap=16,
        p=20,
    )
