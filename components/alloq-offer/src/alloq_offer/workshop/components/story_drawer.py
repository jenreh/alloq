"""Editor of the selected story in the side column."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.list_view import inspector, inspector_section

import appkit_mantine as mn
from alloq_offer.workshop.states.map_proposal_state import MapProposalState
from alloq_offer.workshop.states.map_state import SENTENCE_HINT, MapState

DRAWER_LABEL = "Story bearbeiten"
SPLIT = "Aufteilen"
SPLIT_AI = "KI-Aufteilung vorschlagen"
ARCHIVE = "Archivieren"
CLOSE = "Schließen"
EXPAND = "Verbreitern"
COLLAPSE = "Verschmälern"
SAVE = "Speichern"
TITLE_LABEL = "Titel"
DESCRIPTION_LABEL = "Beschreibung"
DESCRIPTION_PLACEHOLDER = "Hintergrund, Hinweise, offene Fragen"
ORIGIN_TITLE = "Herkunft"
WRAPPED_FIELDS = frozenset({"benefit"})
"""Story parts shown as growing text areas; line breaks become spaces on save."""
FIELDS = (
    ("role", "Als", "Rolle"),
    ("goal", "möchte ich", "Ziel oder Handlung"),
    ("benefit", "um", "Nutzen"),
)


def _field(name: str, label: str, placeholder: str) -> rx.Component:
    story = MapState.selected
    if name in WRAPPED_FIELDS:
        return mn.textarea(
            label=label,
            placeholder=placeholder,
            name=name,
            default_value=story[name].to(str),
            autosize=True,
            min_rows=2,
            custom_attrs={"maxLength": 300},
        )
    return mn.text_input(
        label=label,
        placeholder=placeholder,
        name=name,
        default_value=story[name].to(str),
        custom_attrs={"maxLength": 300},
    )


def _icon(icon: str, label: str, **props: Any) -> rx.Component:
    return mn.action_icon(
        rx.icon(icon, size=16),
        variant="subtle",
        size="md",
        aria_label=label,
        custom_attrs={"title": label},
        **props,
    )


def _header() -> rx.Component:
    """Key, editable title and the actions; stays on top while the body scrolls."""
    story = MapState.selected
    return mn.box(
        mn.group(
            mn.text(
                story["key"].to(str), fz="11.5px", c=theme.TEXT_MUTED, ff="monospace"
            ),
            mn.group(
                mn.action_icon(
                    rx.icon(
                        rx.cond(
                            MapState.drawer_wide, "panel-left-open", "panel-left-close"
                        ),
                        size=16,
                    ),
                    variant="subtle",
                    size="md",
                    color="gray",
                    type="button",
                    aria_label=rx.cond(MapState.drawer_wide, COLLAPSE, EXPAND),
                    custom_attrs={
                        "title": rx.cond(MapState.drawer_wide, COLLAPSE, EXPAND)
                    },
                    on_click=MapState.toggle_drawer_width,
                ),
                _icon(
                    "save", SAVE, color="blue", type="submit", loading=MapState.saving
                ),
                _icon(
                    "archive", ARCHIVE, color="red", on_click=MapState.archive_selected
                ),
                _icon("x", CLOSE, color="gray", on_click=MapState.close_story),
                gap=2,
                wrap="nowrap",
            ),
            justify="space-between",
            wrap="nowrap",
        ),
        mn.textarea(
            name="title",
            default_value=story["title"].to(str),
            variant="unstyled",
            autosize=True,
            min_rows=2,
            custom_attrs={
                "maxLength": 300,
                "aria-label": TITLE_LABEL,
                "title": story["title"].to(str),
            },
            class_name="aq-map-title aq-story-title",
        ),
        class_name="aq-insp-head",
    )


def _place(label: str, options: Any, value: Any, name: str) -> rx.Component:
    return mn.select(
        label=label,
        data=options,
        value=value,
        allow_deselect=False,
        size="sm",
        on_change=lambda picked: (  # ty: ignore[invalid-argument-type]
            MapState.place_story(picked, MapState.selected["slice_id"].to(str))
            if name == "task"
            else MapState.place_story(MapState.selected["task_id"].to(str), picked)
        ),
    )


def story_drawer() -> rx.Component:
    story = MapState.selected
    return inspector(
        rx.form(
            _header(),
            _body(story),
            on_submit=MapState.save_story,
            # A new story or revision resets the uncontrolled fields.
            key=story["key"].to(str) + "-" + MapState.revision.to(str),
            class_name="aq-insp-form",
        ),
        label=DRAWER_LABEL,
        wide=MapState.drawer_wide,
    )


def _body(story: Any) -> rx.Component:
    return rx.fragment(
        inspector_section(
            "User Story",
            *(_field(*field) for field in FIELDS),
            mn.text(SENTENCE_HINT, fz="12px", c=theme.TEXT_MUTED),
            mn.textarea(
                name="description",
                label=DESCRIPTION_LABEL,
                placeholder=DESCRIPTION_PLACEHOLDER,
                default_value=story["description"].to(str),
                autosize=True,
                min_rows=3,
                max_rows=12,
                custom_attrs={"maxLength": 4000},
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
                SPLIT,
                variant="default",
                size="xs",
                loading=MapState.saving,
                on_click=MapState.split_selected,
            ),
            mn.button(
                SPLIT_AI,
                variant="default",
                size="xs",
                on_click=MapProposalState.propose_split,
            ),
            gap=8,
            wrap="nowrap",
            class_name="aq-insp-foot",
        ),
    )
