"""Offer list (macOS table) with state groups and the inspector."""

import reflex as rx
from alloq_commons import theme
from alloq_commons.access import offers_only
from alloq_commons.components.list_view import (
    badge,
    cell_main,
    list_group,
    list_header,
    list_row,
    number,
    plain_button,
    split_view,
    sticky_block_header,
)
from alloq_commons.components.toolbar import primary_button
from reflex.vars import ArrayVar, ObjectVar

import appkit_mantine as mn
from alloq_offer.components.offer_inspector import offer_inspector
from alloq_offer.components.offer_parts import (
    EMPTY_ALL,
    EMPTY_ALL_HINT,
    EMPTY_FILTERED,
    EMPTY_FILTERED_HINT,
    RESET_FILTERS,
    date_or_dash,
    days,
    euro,
    state_badge,
)
from alloq_offer.entities import OfferStateEnum
from alloq_offer.models import Offer
from alloq_offer.services.offers import FILTER_ARCHIVED
from alloq_offer.states.offer_state import OfferState

TEMPLATE = "minmax(0, 2fr) minmax(0, 1fr) 56px 108px 84px 100px 100px 104px"
COLUMNS: list[tuple[str, str, bool]] = [
    ("Angebot", "title", False),
    ("Key Accounter", "key_accounter", False),
    ("CIU", "ciu", False),
    ("Status", "state", False),
    ("PT", "person_days", True),
    ("HK", "production_cost", True),
    ("VK", "recommended_price", True),
    ("Versendet am", "sent_date", True),
]
GROUPS: list[tuple[str, str]] = [
    (OfferStateEnum.NEW.value, "new_rows"),
    (OfferStateEnum.IN_PROGRESS.value, "in_progress_rows"),
    (OfferStateEnum.SENT.value, "sent_rows"),
    (FILTER_ARCHIVED, "archived_rows"),
]


def _row(offer: ObjectVar[Offer]) -> rx.Component:
    selected = OfferState.inspected.to(Offer).id == offer.id
    return list_row(
        cell_main(rx.fragment(), offer.title, offer.customer),
        rx.el.span(offer.key_accounter, class_name="aq-cell-text"),
        rx.el.span(badge(offer.ciu, "neutral")),
        rx.el.span(state_badge(offer.state)),
        number(days(offer.person_days + offer.risk_buffer_days), fontWeight="600"),
        number(euro(offer.production_cost)),
        number(euro(offer.recommended_price)),
        number(date_or_dash(offer.sent_date.to(str)), color=theme.TEXT_MUTED),
        template=TEMPLATE,
        selected=selected,
        on_click=OfferState.inspect(offer.id),
        on_double_click=OfferState.open_edit_modal(offer.id),
    )


def _group(title: str, rows: ArrayVar) -> rx.Component:
    return rx.cond(
        rows.length() > 0,
        mn.box(
            list_group(title, rows.length(), style=sticky_block_header("30px")),
            rx.foreach(rows, _row),
        ),
        rx.fragment(),
    )


def _total_row() -> rx.Component:
    return rx.el.div(
        rx.el.span("Summe", style={"gridColumn": "span 4"}),
        number(days(OfferState.total_person_days)),
        number(euro(OfferState.total_production_cost)),
        number(euro(OfferState.total_recommended_price)),
        rx.fragment(),
        class_name="aq-tfoot",
        style={"gridTemplateColumns": TEMPLATE},
        custom_attrs={"role": "row"},
    )


def _empty_state(
    icon: str, title: str, hint: str, action: rx.Component
) -> rx.Component:
    return mn.stack(
        mn.theme_icon(
            rx.icon(icon, size=22),
            size=48,
            radius="xl",
            variant="light",
            color="gray",
        ),
        mn.stack(
            mn.text(title, fz="15px", fw="600", ta="center"),
            mn.text(hint, fz="13px", c=theme.TEXT_MUTED, ta="center"),
            gap=4,
            align="center",
        ),
        action,
        gap="md",
        align="center",
        justify="center",
        py=64,
        px=22,
        class_name="aq-offer-empty",
    )


def _no_matches() -> rx.Component:
    return _empty_state(
        "search-x",
        EMPTY_FILTERED,
        EMPTY_FILTERED_HINT,
        plain_button(RESET_FILTERS, OfferState.reset_filters),
    )


def _no_offers() -> rx.Component:
    return _empty_state(
        "file-text",
        EMPTY_ALL,
        EMPTY_ALL_HINT,
        offers_only(
            primary_button("Angebot anlegen", "plus", OfferState.open_create_modal)
        ),
    )


def offer_list() -> rx.Component:
    return mn.box(
        list_header(
            COLUMNS,
            TEMPLATE,
            sort_column=OfferState.sort_column,
            sort_desc=OfferState.sort_desc,
            on_sort=OfferState.toggle_sort,
        ),
        *(_group(title, getattr(OfferState, rows)) for title, rows in GROUPS),
        rx.cond(OfferState.row_count == 0, _no_matches(), _total_row()),
        class_name="aq-offer-list",
    )


def offer_table() -> rx.Component:
    """List view of all offers with the inspector on the right."""
    return rx.cond(
        OfferState.is_loading & (OfferState.offers.length() == 0),
        mn.center(mn.loader(size="sm"), py="xl", flex="1"),
        rx.cond(
            OfferState.offers.length() == 0,
            _no_offers(),
            split_view(
                offer_list(),
                offer_inspector(),
                show_inspector=OfferState.show_inspector,
            ),
        ),
    )
