"""Tab "Story Map": the editable map; the selected story opens on the right."""

import reflex as rx
from alloq_commons import theme

import appkit_mantine as mn
from alloq_offer.workshop.components.map_view import map_section
from alloq_offer.workshop.components.story_drawer import story_drawer
from alloq_offer.workshop.states.map_state import MapState
from alloq_offer.workshop.states.workshop_state import TAB_DRAFT, WorkshopState

NO_MAP_TITLE = "Noch keine Story Map"
NO_MAP_TEXT = (
    "Die Story Map entsteht mit dem ersten Entwurf aus den Quellen. Fügen Sie im "
    "Tab „Entwurf“ Quellen hinzu und erzeugen Sie den Entwurf."
)
TO_DRAFT = "Zum Entwurf"


def _no_map() -> rx.Component:
    return mn.stack(
        mn.text(NO_MAP_TITLE, fz="18px", fw=650),
        mn.text(NO_MAP_TEXT, c=theme.TEXT_MUTED, lh="1.5", maw=560),
        mn.group(
            mn.button(TO_DRAFT, on_click=WorkshopState.set_tab(TAB_DRAFT)),
        ),
        gap=12,
        p=28,
        style=theme.CARD,
    )


def map_tab() -> rx.Component:
    return rx.box(
        rx.box(
            rx.cond(MapState.has_map, map_section(), _no_map()),
            class_name="aq-split-main aq-ws-pad",
        ),
        rx.cond(MapState.has_selection, story_drawer()),
        class_name="aq-split",
    )
