"""Page "Angebote" in the administration: templates, chapter blocks and prompts."""

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import segmented, window_toolbar

import appkit_mantine as mn
from alloq_offer.admin.components.blocks import blocks_table
from alloq_offer.admin.components.prompts import prompts_tab
from alloq_offer.admin.components.templates import templates_tab
from alloq_offer.admin.states.block_admin_state import BlockAdminState
from alloq_offer.admin.states.offer_admin_state import (
    TAB_BLOCKS,
    TAB_PROMPTS,
    TABS,
    OfferAdminState,
)
from alloq_offer.admin.states.prompt_admin_state import PromptAdminState
from alloq_offer.admin.states.template_admin_state import TemplateAdminState
from appkit_user.authentication.components.components import requires_admin

OFFER_ADMIN_ROUTE = "/admin/offers"
TITLE = "Angebote"
SUBTITLE = "Administration · Vorlagen, Kapitelbausteine und KI-Prompts"


def create_offer_admin_page(
    sidebar: rx.Component,
    route: str = OFFER_ADMIN_ROUTE,
    title: str = TITLE,
) -> rx.Component:
    """Page factory for the offer administration."""

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            TITLE,
            SUBTITLE,
            center=segmented(OfferAdminState.tab, OfferAdminState.set_tab, TABS),
        ),
        admin_only=True,
        on_load=[
            TemplateAdminState.load_templates,
            BlockAdminState.load_blocks,
            PromptAdminState.load_prompts,
        ],
    )
    def _offer_admin_page() -> rx.Component:
        return requires_admin(
            mn.box(
                rx.match(
                    OfferAdminState.tab,
                    (TAB_BLOCKS, blocks_table()),
                    (TAB_PROMPTS, prompts_tab()),
                    templates_tab(),
                ),
                p=20,
                w="100%",
                max_width="1400px",
                style={"overflow": "auto", "background": theme.BACKGROUND},
            ),
        )

    return _offer_admin_page
