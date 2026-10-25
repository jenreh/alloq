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
LOADING_MAP = "Die Story Map wird geladen"


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


def _skeleton() -> rx.Component:
    """Placeholder cards in the shape of the map while it loads."""
    return rx.box(
        *(
            mn.stack(
                mn.skeleton(height=24, width="70%"),
                *(mn.skeleton(height=56) for _ in range(rows)),
                gap=8,
            )
            for rows in (4, 3, 4, 2, 3)
        ),
        class_name="aq-map-skeleton aq-map-empty",
        custom_attrs={"aria-busy": "true", "aria-label": LOADING_MAP},
    )


def map_tab() -> rx.Component:
    return rx.box(
        rx.box(
            rx.cond(
                MapState.map_loaded,
                rx.cond(
                    MapState.has_map,
                    map_section(),
                    rx.box(_no_map(), class_name="aq-ws-pad aq-map-empty"),
                ),
                _skeleton(),
            ),
            class_name="aq-split-main aq-map-main",
        ),
        rx.cond(MapState.has_selection, story_drawer()),
        class_name="aq-split",
    )
