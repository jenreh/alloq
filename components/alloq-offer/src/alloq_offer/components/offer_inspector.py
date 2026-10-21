"""Inspector on the right of the offer list."""

import reflex as rx
from alloq_commons import theme
from alloq_commons.access import CAN_EDIT_OFFERS, offers_only
from alloq_commons.components.list_view import (
    inspector,
    inspector_section,
    key_values,
    plain_button,
    tag,
)
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.components.offer_parts import (
    NO_SELECTION,
    days,
    euro,
    state_badge,
)
from alloq_offer.entities import OfferStateEnum
from alloq_offer.models import Offer
from alloq_offer.states.offer_state import OfferState

STATE_OPTIONS: list[str] = [s.value for s in OfferStateEnum]


def _selected() -> ObjectVar[Offer]:
    return OfferState.inspected.to(Offer)


def _heading(offer: ObjectVar[Offer]) -> rx.Component:
    return mn.group(
        mn.stack(
            mn.text(offer.title, fz="15px", fw=650, lh="1.25", line_clamp=2),
            mn.text(offer.customer, fz="11.5px", c=theme.TEXT_MUTED, truncate="end"),
            gap=2,
            miw=0,
            flex="1",
        ),
        rx.cond(offer.archived, tag("Archiviert"), rx.fragment()),
        state_badge(offer.state),
        gap=10,
        wrap="nowrap",
        align="center",
    )


def _actions(offer: ObjectVar[Offer]) -> rx.Component:
    return offers_only(
        mn.group(
            plain_button("Bearbeiten", OfferState.open_edit_modal(offer.id), flex="1"),
            rx.cond(
                offer.archived,
                plain_button(
                    "Wiederherstellen",
                    OfferState.restore_offer(offer.id),
                    flex="1",
                ),
                plain_button(
                    "Archivieren", OfferState.archive_offer(offer.id), flex="1"
                ),
            ),
            gap=8,
            wrap="nowrap",
        )
    )


def _copy_icon(value: rx.Var[str], label: str) -> rx.Component:
    return mn.action_icon(
        rx.icon("copy", size=13, stroke_width=1.8),
        variant="subtle",
        color="gray",
        size=20,
        aria_label=label,
        title=label,
        on_click=[
            rx.set_clipboard(value),
            rx.toast.success("Link kopiert", position="top-right"),
        ],
    )


def _sharepoint(offer: ObjectVar[Offer]) -> rx.Component:
    url = offer.sharepoint_url.to(str)
    return rx.cond(
        url != "",
        mn.group(
            rx.el.a(
                "Öffnen",
                href=url,
                target="_blank",
                rel="noopener noreferrer",
                style={"color": theme.ACCENT},
            ),
            _copy_icon(url, "SharePoint-Link kopieren"),
            gap=4,
            wrap="nowrap",
        ),
        mn.text("–", fz="inherit", lh="inherit", c=theme.TEXT_MUTED),
    )


def _sent_date_input(offer: ObjectVar[Offer]) -> rx.Component:
    return mn.date_input(
        value=OfferState.inspected_sent_date,
        on_change=lambda value: OfferState.set_inspected_sent_date(offer.id, value),
        on_blur=OfferState.save_inspected_sent_date(offer.id),
        right_section=offers_only(
            mn.action_icon(
                rx.icon("calendar-check", size=14, stroke_width=1.8),
                variant="subtle",
                color="gray",
                size=22,
                aria_label="Heute",
                title="Heute",
                on_click=[
                    OfferState.set_sent_date_today(offer.id),
                    OfferState.save_inspected_sent_date(offer.id),
                ],
            )
        ),
        disabled=~CAN_EDIT_OFFERS,
        right_section_pointer_events="all",
        clearable=False,
        locale="de",
        value_format="DD.MM.YYYY",
        size="xs",
    )


def _details(offer: ObjectVar[Offer]) -> rx.Component:
    return mn.stack(
        _heading(offer),
        _actions(offer),
        inspector_section(
            "Eckdaten",
            key_values(
                (
                    "Status",
                    mn.select(
                        data=STATE_OPTIONS,
                        value=offer.state,
                        on_change=OfferState.update_inspected_state(offer.id),
                        disabled=~CAN_EDIT_OFFERS,
                        clearable=False,
                        size="xs",
                    ),
                ),
                ("Versendet am", _sent_date_input(offer)),
                ("CIU", OfferState.inspected_ciu_label),
                ("Key Accounter", offer.key_accounter),
                ("SharePoint", _sharepoint(offer)),
            ),
        ),
        inspector_section(
            "Kalkulation",
            key_values(
                ("PT", days(offer.person_days)),
                ("Risikopuffer", days(offer.risk_buffer_days)),
                ("Gesamt-PT", days(OfferState.inspected_total_days)),
                ("HK", euro(offer.production_cost)),
                ("Empfohlener VK", euro(offer.recommended_price)),
                ("Marge", OfferState.inspected_margin),
            ),
        ),
        gap=18,
    )


def offer_inspector() -> rx.Component:
    return inspector(
        rx.cond(
            OfferState.inspected,
            _details(_selected()),
            mn.text(NO_SELECTION, fz="12.5px", c=theme.TEXT_MUTED),
        ),
        label="Angebotsdetails",
    )
