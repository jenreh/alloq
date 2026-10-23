"""Editor of the selected story in the side column."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.list_view import inspector, inspector_section
from alloq_commons.components.toolbar import segmented

import appkit_mantine as mn
from alloq_offer.workshop.states.map_state import SCOPES, SENTENCE_HINT, MapState

DRAWER_LABEL = "Story bearbeiten"
SCOPE_TITLE = "Umfang"
SPLIT = "Aufteilen"
ARCHIVE = "Archivieren"
CLOSE = "Schließen"
ORIGIN_TITLE = "Herkunft"
FIELDS = (
    ("title", "Titel", ""),
    ("role", "Als", "Rolle"),
    ("goal", "möchte ich", "Ziel oder Handlung"),
    ("benefit", "um", "Nutzen"),
)


def _field(name: str, label: str, placeholder: str) -> rx.Component:
    story = MapState.selected
    return mn.text_input(
        label=label,
        placeholder=placeholder,
        default_value=story[name].to(str),
        key=story["key"].to(str) + name + MapState.revision.to(str),
        on_blur=lambda value: MapState.save_story_field(name, value),  # ty: ignore[invalid-argument-type]
        custom_attrs={"maxLength": 300},
    )


def _place(label: str, options: Any, value: Any, name: str) -> rx.Component:
    return mn.select(
        label=label,
        data=options,
        value=value,
        allow_deselect=False,
        on_change=lambda picked: (  # ty: ignore[invalid-argument-type]
            MapState.place_story(picked, MapState.selected["slice_id"].to(str))
            if name == "task"
            else MapState.place_story(MapState.selected["task_id"].to(str), picked)
        ),
    )


def story_drawer() -> rx.Component:
    story = MapState.selected
    return inspector(
        inspector_section(
            story["key"].to(str),
            mn.text(story["title"], fw=650, fz="16px"),
            *(_field(*field) for field in FIELDS),
            mn.box(
                story["sentence"].to(str),
                p=12,
                style={"background": theme.SURFACE_MUTED, "borderRadius": "10px"},
            ),
            mn.text(SENTENCE_HINT, fz="12px", c=theme.TEXT_MUTED),
        ),
        inspector_section(
            SCOPE_TITLE,
            segmented(
                story["scope"].to(str),
                MapState.set_scope,
                [{"value": scope, "label": scope} for scope in SCOPES],
            ),
        ),
        inspector_section(
            "Einordnung",
            _place(
                "Aktivität und Aufgabe",
                MapState.task_options,
                story["task_id"].to(str),
                "task",
            ),
            _place(
                "Umsetzungsschnitt",
                MapState.slice_options,
                story["slice_id"].to(str),
                "slice",
            ),
        ),
        inspector_section(
            ORIGIN_TITLE,
            mn.text(story["origin"].to(str) + " · " + story["refs"].to(str), fz="13px"),
        ),
        mn.group(
            mn.button(
                SPLIT, variant="default", size="xs", on_click=MapState.split_selected
            ),
            mn.button(
                ARCHIVE,
                variant="subtle",
                color="red",
                size="xs",
                on_click=MapState.archive_selected,
            ),
            mn.button(
                CLOSE, variant="subtle", size="xs", on_click=MapState.close_story
            ),
        ),
        label=DRAWER_LABEL,
    )
