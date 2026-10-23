"""Body of the workshop page: tabs and their content."""

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.list_view import empty_list
from alloq_commons.components.toolbar import segmented

import appkit_mantine as mn
from alloq_offer.workshop.components.briefing_tab import briefing_tab
from alloq_offer.workshop.components.chapters_tab import chapters_tab
from alloq_offer.workshop.components.draft_tab import draft_tab
from alloq_offer.workshop.components.export_tab import export_tab
from alloq_offer.workshop.states.workshop_state import (
    TAB_BRIEFING,
    TAB_CHAPTERS,
    TAB_DRAFT,
    TAB_EXPORT,
    TABS,
    WorkshopState,
)

NOT_FOUND_TEXT = "Dieses Angebot gibt es nicht."


def workshop_tabs() -> rx.Component:
    return segmented(WorkshopState.active_tab, WorkshopState.set_tab, TABS)


def workshop_body() -> rx.Component:
    return rx.box(_workshop_content(), class_name="aq-ws")


def _workshop_content() -> rx.Component:
    return rx.cond(
        WorkshopState.not_found,
        mn.box(empty_list(NOT_FOUND_TEXT), p=20),
        rx.cond(
            WorkshopState.loaded,
            rx.match(
                WorkshopState.active_tab,
                (TAB_DRAFT, draft_tab()),
                (TAB_CHAPTERS, chapters_tab()),
                (TAB_BRIEFING, briefing_tab()),
                (TAB_EXPORT, export_tab()),
                draft_tab(),
            ),
            mn.box(mn.loader(size="sm"), p=20, c=theme.TEXT_MUTED),
        ),
    )
