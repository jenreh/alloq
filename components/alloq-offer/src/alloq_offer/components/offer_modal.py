"""Create and edit modal of an offer."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.forms import section
from alloq_commons.components.modal_layout import (
    MODAL_CLASS,
    modal_footer,
    modal_form_layout,
)
from reflex.event import EventType

import appkit_mantine as mn
from alloq_offer.entities import OfferStateEnum
from alloq_offer.states.offer_state import OfferState

TITLE_CREATE = "Neues Angebot"
TITLE_EDIT = "Angebot bearbeiten"
TITLE_ACCEPT = "Angebot annehmen"
ACCEPT_HINT = "Aus dem Angebot wird ein Projekt im Status Geplant angelegt."
STATE_OPTIONS: list[str] = [s.value for s in OfferStateEnum]


def _text(name: str, label: str, *, required: bool = True, limit: int = 255, **kw):  # noqa: ANN003, ANN202
    return mn.text_input(
        name=name,
        label=label,
        default_value=OfferState.form[name],
        on_blur=lambda value: OfferState.set_form_field(name, value),
        required=required,
        custom_attrs={"maxLength": limit},
        **kw,
    )


def _number(name: str, label: str, *, required: bool = True, **kw):  # noqa: ANN003, ANN202
    return mn.number_input(
        name=name,
        label=label,
        default_value=OfferState.form[name].to(float),
        on_change=lambda value: OfferState.set_form_field(name, value),
        required=required,
        min=0,
        decimal_scale=2,
        decimal_separator=",",
        thousand_separator=".",
        allow_negative=False,
        **kw,
    )


def offer_form_fields() -> rx.Component:
    return mn.flex(
        section(
            _text("title", "Angebotstitel", placeholder="z.B. Datenplattform"),
            _text("customer", "Kunde", placeholder="z.B. Muster AG"),
            _text("key_accounter", "Account Manager"),
            mn.select(
                name="industry_id",
                label="Branche",
                description="Die Liste pflegen Admins unter Administration · Branchen.",
                data=OfferState.industry_options,
                default_value=OfferState.form["industry_id"],
                on_change=lambda value: OfferState.set_form_field("industry_id", value),
                required=True,
                clearable=False,
            ),
        ),
        section(
            _number("person_days", "Kalkulierte Personentage"),
            _number("risk_buffer_days", "Risikopuffer (Personentage)", required=False),
            _number("production_cost", "Kosten", suffix=" €"),
            _number("recommended_price", "Empfohlener Preis", suffix=" €"),
        ),
        section(
            mn.select(
                name="state",
                label="Status",
                data=STATE_OPTIONS,
                default_value=OfferState.form["state"],
                on_change=lambda value: OfferState.set_form_field("state", value),
                required=True,
                clearable=False,
            ),
            mn.date_input(
                label="Versendet am",
                value=OfferState.form["sent_date"],
                on_change=lambda value: OfferState.set_form_field("sent_date", value),
                clearable=True,
                locale="de",
                value_format="DD.MM.YYYY",
                left_section=rx.icon("calendar", size=16),
            ),
            _text(
                "sharepoint_url",
                "Link zu den Dokumenten",
                required=False,
                limit=2048,
                placeholder="https://",
            ),
        ),
        direction="column",
        width="100%",
        gap="md",
    )


def _form(on_submit: EventType[Any]) -> rx.Component:
    return modal_form_layout(
        content=mn.flex(
            offer_form_fields(),
            mn.space(height="1.5rem"),
            direction="column",
            width="100%",
            key=OfferState.form_version.to(str),
        ),
        footer=modal_footer(
            "Angebot speichern",
            OfferState.close_modal,
            disabled=OfferState.is_form_invalid,
        ),
        on_submit=on_submit,
    )


def offer_modal() -> rx.Component:
    return mn.modal(
        rx.cond(
            OfferState.editing_id > 0,
            _form(OfferState.update_offer),
            _form(OfferState.create_offer),
        ),
        title=rx.cond(OfferState.editing_id > 0, TITLE_EDIT, TITLE_CREATE),
        opened=OfferState.form_open,
        on_close=OfferState.close_modal,
        size="lg",
        centered=True,
        class_name=MODAL_CLASS,
        overlay_props={"backgroundOpacity": 0.5, "blur": 4},
    )


def _accept_date(name: str, label: str) -> rx.Component:
    return mn.date_input(
        name=name,
        label=label,
        value=OfferState.accept_form[name],
        on_change=lambda value: OfferState.set_accept_field(name, value),
        required=True,
        clearable=False,
        locale="de",
        value_format="DD.MM.YYYY",
        left_section=rx.icon("calendar", size=16),
    )


def accept_modal() -> rx.Component:
    """Ask for the project code and period when an offer is accepted."""
    return mn.modal(
        modal_form_layout(
            content=mn.stack(
                mn.text(ACCEPT_HINT, fz="13px", c=theme.TEXT_MUTED),
                mn.text_input(
                    name="code",
                    label="Projektkürzel",
                    default_value=OfferState.accept_form["code"],
                    on_blur=lambda value: OfferState.set_accept_field("code", value),
                    required=True,
                    custom_attrs={"maxLength": 50},
                ),
                _accept_date("start_date", "Projektstart"),
                _accept_date("end_date", "Projektende"),
                gap="md",
            ),
            footer=modal_footer(
                "Projekt anlegen",
                OfferState.close_accept_modal,
                disabled=OfferState.is_accept_invalid,
            ),
            on_submit=OfferState.accept_offer,
        ),
        title=TITLE_ACCEPT,
        opened=OfferState.accept_open,
        on_close=OfferState.close_accept_modal,
        size="md",
        centered=True,
        class_name=MODAL_CLASS,
        overlay_props={"backgroundOpacity": 0.5, "blur": 4},
    )
