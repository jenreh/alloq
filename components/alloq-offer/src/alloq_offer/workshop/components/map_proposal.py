"""AI proposals for the map: a request row and the comparison card."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.workshop.states.map_proposal_state import MapProposalState

PROPOSE_TITLE = "KI-Vorschlag für die Map"
INSTRUCTION_PLACEHOLDER = "Fehlende Prozessschritte (oder eigene Anweisung)"
PROPOSE_BUTTON = "Vorschlagen"
PROPOSAL_TITLE = "Vorschlag der KI"
PROPOSAL_HINT = (
    "Der Vorschlag ergänzt die Map um neue Elemente. Bestehendes bleibt unverändert."
)
STALE_HINT = "Veraltet: Die Map wurde seit diesem Vorschlag geändert."
ACCEPT = "Übernehmen"
REJECT = "Verwerfen"
SPLIT_BUTTON = "Aufteilung vorschlagen"
POLL_MS = 3000
KIND_COLORS = {"Aktivität": "blue", "Aufgabe": "gray", "Story": "green"}

Row = ObjectVar[dict[str, Any]]


def _line(line: Row) -> rx.Component:
    return mn.group(
        mn.badge(
            line["kind"].to(str),
            color=rx.match(line["kind"].to(str), *KIND_COLORS.items(), "gray"),
            variant="light",
            size="xs",
        ),
        mn.text(line["text"].to(str), fz="13px", lh="1.45"),
        wrap="nowrap",
        align="flex-start",
        gap=8,
    )


def _proposal_card() -> rx.Component:
    return mn.stack(
        mn.text(PROPOSAL_TITLE, fw=650, fz="14px"),
        mn.text(
            rx.cond(
                MapProposalState.is_stale,
                STALE_HINT,
                PROPOSAL_HINT,
            ),
            fz="12px",
            c=rx.cond(MapProposalState.is_stale, theme.WARNING, theme.TEXT_MUTED),
        ),
        mn.stack(
            rx.foreach(
                MapProposalState.proposal["lines"].to(list[dict[str, Any]]), _line
            ),
            gap=6,
        ),
        mn.group(
            mn.button(
                ACCEPT,
                size="xs",
                disabled=MapProposalState.is_stale,
                on_click=MapProposalState.accept_proposal,
            ),
            mn.button(
                REJECT,
                size="xs",
                variant="default",
                on_click=MapProposalState.reject_proposal,
            ),
            gap=6,
        ),
        gap=8,
    )


def map_proposal() -> rx.Component:
    """Request row for a new proposal, shown in the map footer."""
    return mn.group(
        mn.text(PROPOSE_TITLE, fz="12px", c=theme.TEXT_MUTED),
        mn.text_input(
            placeholder=INSTRUCTION_PLACEHOLDER,
            value=MapProposalState.instruction,
            on_change=MapProposalState.set_instruction,
            size="xs",
            w=320,
            custom_attrs={"aria-label": PROPOSE_TITLE},
        ),
        mn.button(
            PROPOSE_BUTTON,
            size="xs",
            variant="default",
            loading=MapProposalState.working,
            on_click=MapProposalState.propose_steps,
        ),
        rx.cond(
            MapProposalState.working,
            rx.moment(
                interval=POLL_MS,
                on_change=MapProposalState.refresh_proposal,
                display="none",
            ),
        ),
        gap=8,
        wrap="nowrap",
    )


def map_proposal_panel() -> rx.Component:
    """The open proposal as a strip between the map and its footer."""
    return rx.cond(
        MapProposalState.has_proposal,
        rx.box(_proposal_card(), class_name="aq-map-proposal"),
    )
