"""Page factory of the offer workshop."""

import reflex as rx
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar
from alloq_commons.roles import OFFER_EDITOR_ROLE

import appkit_mantine as mn
from alloq_offer.workshop.components.workshop_view import (
    workshop_body,
    workshop_scope,
    workshop_tabs,
)
from alloq_offer.workshop.routes import WORKSHOP_ROUTE
from alloq_offer.workshop.states.briefing_state import BriefingState
from alloq_offer.workshop.states.chapter_state import ChapterState
from alloq_offer.workshop.states.draft_state import DraftState
from alloq_offer.workshop.states.export_state import ExportState
from alloq_offer.workshop.states.map_proposal_state import MapProposalState
from alloq_offer.workshop.states.map_state import MapState
from alloq_offer.workshop.states.review_state import ReviewState
from alloq_offer.workshop.states.sources_state import SourcesState
from alloq_offer.workshop.states.workshop_state import WorkshopState
from appkit_user.authentication.components.components import requires_role

BACK_LABEL = "Angebote"
NO_ACCESS = "Die Werkstatt ist nur für Angebotsbearbeiter verfügbar."


def create_offer_workshop_page(
    sidebar: rx.Component,
    route: str = WORKSHOP_ROUTE,
    title: str = "Angebotswerkstatt",
) -> rx.Component:

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            WorkshopState.offer_title,
            WorkshopState.subtitle,
            center=workshop_tabs(),
            actions=[
                rx.link(
                    mn.button(BACK_LABEL, variant="default", size="xs", h=28),
                    href="/offers",
                )
            ],
        ),
        scope=workshop_scope(),
        padded=False,
        # Events of one client run one after another: the "Entwurf" tab first,
        # the slow chapter and check loads last.
        on_load=[
            WorkshopState.load_workshop,
            DraftState.load_overview,
            SourcesState.load_sources,
            MapState.load_map,
            MapProposalState.load_proposal,
            BriefingState.load_briefing,
            ExportState.load_exports,
            ChapterState.load_chapters,
            ReviewState.run_checks,
            DraftState.load_overview,
        ],
    )
    def _workshop_page() -> rx.Component:
        return requires_role(
            workshop_body(),
            role=OFFER_EDITOR_ROLE.name,
            fallback=mn.box(mn.text(NO_ACCESS), p=20),
        )

    return _workshop_page
