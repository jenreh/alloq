"""Body of the workshop page: tabs and their content."""

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.list_view import empty_list
from alloq_commons.components.toolbar import segmented

import appkit_mantine as mn
from alloq_offer.workshop.components.briefing_tab import briefing_tab
from alloq_offer.workshop.components.draft_tab import draft_tab
from alloq_offer.workshop.states.workshop_state import (
    TAB_BRIEFING,
    TAB_CHAPTERS,
    TAB_DRAFT,
    TAB_EXPORT,
    TABS,
    WorkshopState,
)

NOT_FOUND_TEXT = "Dieses Angebot gibt es nicht."
COMING_SOON = "Dieser Bereich folgt in einem der nächsten Ausbauschritte."


def workshop_tabs() -> rx.Component:
    return segmented(WorkshopState.active_tab, WorkshopState.set_tab, TABS)


def _later_tab() -> rx.Component:
    return mn.box(empty_list(COMING_SOON), p=20)


def workshop_body() -> rx.Component:
    return rx.cond(
        WorkshopState.not_found,
        mn.box(empty_list(NOT_FOUND_TEXT), p=20),
        rx.cond(
            WorkshopState.loaded,
            rx.match(
                WorkshopState.active_tab,
                (TAB_DRAFT, draft_tab()),
                (TAB_CHAPTERS, _later_tab()),
                (TAB_BRIEFING, briefing_tab()),
                (TAB_EXPORT, _later_tab()),
                draft_tab(),
            ),
            mn.box(mn.loader(size="sm"), p=20, c=theme.TEXT_MUTED),
        ),
    )
