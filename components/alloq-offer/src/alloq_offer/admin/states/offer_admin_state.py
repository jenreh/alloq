"""The tab shown in the "Angebote" administration."""

import reflex as rx

TAB_TEMPLATES = "templates"
TAB_BLOCKS = "blocks"
TAB_PROMPTS = "prompts"
TABS: list[dict[str, str]] = [
    {"value": TAB_TEMPLATES, "label": "Vorlagen"},
    {"value": TAB_BLOCKS, "label": "Kapitelbausteine"},
    {"value": TAB_PROMPTS, "label": "Prompts"},
]


class OfferAdminState(rx.State):
    tab: rx.Field[str] = rx.field(TAB_TEMPLATES)

    @rx.event
    def set_tab(self, value: str) -> None:
        self.tab = value
