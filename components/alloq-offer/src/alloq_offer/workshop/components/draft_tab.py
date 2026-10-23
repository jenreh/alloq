"""Tab "Entwurf & Story Map": start card and the sources panel."""

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.list_view import inspector, inspector_section

import appkit_mantine as mn
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
SOURCES_TITLE = "Quellen"
NO_SOURCES = "Noch keine Quellen. Fügen Sie Texte, E-Mails oder Dokumente hinzu."
SOURCES_HINT = (
    "Lücken wie nicht ausgewertete Bilder oder fehlende OCR bleiben sichtbar. "
    "Neue Quellen ändern einen bestehenden Entwurf nur als Vorschlag."
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
                WorkshopState.generate_label,
                size="md",
                radius="md",
                disabled=~WorkshopState.can_generate,
            ),
            mn.checkbox(
                label=AUTO_DRAFT_LABEL,
                checked=WorkshopState.auto_draft,
                on_change=WorkshopState.set_auto_draft,
            ),
            gap=12,
            align="center",
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


def sources_panel() -> rx.Component:
    return inspector(
        inspector_section(
            SOURCES_TITLE,
            mn.text(NO_SOURCES, fz="13px", c=theme.TEXT_MUTED),
            mn.text(SOURCES_HINT, fz="12px", c=theme.TEXT_MUTED, lh="1.5"),
        ),
        label=SOURCES_TITLE,
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
