"""Administration of the industries (Branchen) offers can use."""

from typing import Any

import reflex as rx
from alloq_commons.components.dialogs import delete_dialog
from alloq_commons.components.forms import section
from alloq_commons.components.modal_layout import (
    MODAL_CLASS,
    modal_footer,
    modal_form_layout,
)
from alloq_commons.components.toolbar import primary_button, toolbar_search
from reflex.event import EventType
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.models import Industry
from alloq_offer.states.industry_state import IndustryState
from appkit_ui.styles import sticky_header_style

NAME_HINT = "Wird im Angebot unter „Branche“ zur Auswahl angeboten."


def industry_form_fields(industry: ObjectVar[Industry] | None = None) -> rx.Component:
    return section(
        mn.text_input(
            name="name",
            label="Name",
            description=NAME_HINT,
            default_value=industry.name if industry is not None else "",
            placeholder="z.B. Finanzdienstleistungen",
            required=True,
            custom_attrs={"maxLength": 100},
            left_section=rx.icon("factory", size=16),
        ),
    )


def _industry_modal(
    *,
    title: str,
    opened: rx.Var[bool],
    on_close: EventType[()],
    on_submit: EventType[Any],
    content: rx.Component,
) -> rx.Component:
    return mn.modal(
        modal_form_layout(
            content=mn.flex(
                content,
                mn.space(height="2rem"),
                direction="column",
                width="100%",
            ),
            footer=modal_footer("Branche speichern", on_close),
            on_submit=on_submit,
        ),
        title=title,
        opened=opened,
        on_close=on_close,
        size="md",
        centered=True,
        class_name=MODAL_CLASS,
        overlay_props={"backgroundOpacity": 0.5, "blur": 4},
    )


def add_industry_modal() -> rx.Component:
    return _industry_modal(
        title="Branche hinzufügen",
        opened=IndustryState.add_modal_open,
        on_close=IndustryState.close_add_modal,
        on_submit=IndustryState.create_industry,
        content=industry_form_fields(),
    )


def edit_industry_modal() -> rx.Component:
    return _industry_modal(
        title="Branche bearbeiten",
        opened=IndustryState.edit_modal_open,
        on_close=IndustryState.close_edit_modal,
        on_submit=IndustryState.update_industry,
        content=mn.box(
            industry_form_fields(IndustryState.selected_industry.to(Industry)),
            key=IndustryState.selected_industry.to(Industry).id.to(str),
        ),
    )


def _row(industry: ObjectVar[Industry]) -> rx.Component:
    return mn.table.tr(
        mn.table.td(mn.text(industry.name, size="sm", fw="500")),
        mn.table.td(
            mn.group(
                rx.icon_button(
                    rx.icon("square-pen", size=16),
                    on_click=IndustryState.open_edit_modal(industry.id),
                    variant="ghost",
                ),
                delete_dialog(
                    title="Löschen bestätigen",
                    content=industry.name,
                    on_click=IndustryState.delete_industry(industry.id),
                    icon_button=True,
                    color="red",
                    variant="subtle",
                ),
                gap="xs",
                wrap="nowrap",
                align="center",
            ),
            width="1%",
            style={"whiteSpace": "nowrap"},
        ),
    )


def _loading_row() -> rx.Component:
    return mn.table.tr(
        mn.table.td(
            rx.hstack(
                rx.spinner(size="3"),
                mn.text("Lade Branchen...", size="sm"),
                align="center",
                justify="center",
                spacing="3",
            ),
            col_span=2,
            style={"textAlign": "center"},
        ),
    )


def industries_table() -> rx.Component:
    """List of industries with add, edit and delete."""
    return mn.stack(
        add_industry_modal(),
        edit_industry_modal(),
        mn.table(
            mn.table.thead(
                mn.table.tr(
                    mn.table.th(mn.text("Name", size="sm", fw="700")),
                    mn.table.th(mn.text("", size="sm")),
                    style=sticky_header_style,
                ),
            ),
            mn.table.tbody(
                rx.cond(
                    IndustryState.is_loading,
                    _loading_row(),
                    rx.foreach(IndustryState.filtered_industries, _row),
                )
            ),
            sticky_header=True,
            sticky_header_offset="0px",
            highlight_on_hover=True,
            highlight_on_hover_color=rx.color_mode_cond(
                light="gray.0",
                dark="dark.8",
            ),
            w="100%",
        ),
        w="100%",
    )


def industries_toolbar() -> list[rx.Component]:
    """Toolbar actions of the industries page."""
    return [
        toolbar_search(
            IndustryState.search_filter,
            IndustryState.set_search_filter,
            "Branchen suchen",
        ),
        primary_button("Neue Branche", "plus", IndustryState.open_add_modal),
    ]
