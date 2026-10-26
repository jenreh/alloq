from collections.abc import Callable
from typing import Any

import reflex as rx
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_commons import theme
from alloq_commons.components.formatters import de_number
from alloq_commons.components.toolbar import toolbar_search
from alloq_commons.models import DailyRate
from alloq_commons.models.daily_rate import (
    MAX_CONTRIBUTION_MARGIN_PERCENT,
    MAX_PRICE,
)
from alloq_commons.state.daily_rate_states import DailyRateState
from appkit_ui.styles import sticky_header_style

COST_LABEL = "Herstellkosten"
SALES_LABEL = "Empf. Verkaufspreis"
LIST_LABEL = "Listenpreis"
MIN_MARGIN_LABEL = "Mindest-DB"
MARGIN_LABEL = "DB"
COLUMN_LABELS = ("Rolle", COST_LABEL, SALES_LABEL, LIST_LABEL)
PRICE_HINT = (
    "Preis = Herstellkosten ÷ (1 - DB), aufgerundet auf volle 10 €. "
    "Der Empf. Verkaufspreis rechnet mit dem Mindest-DB, der Listenpreis mit dem "
    "DB; ein eingetragener Listenpreis ersetzt den berechneten."
)
EMPTY_TEXT = "Noch keine Rollen angelegt."

_CURRENCY_INPUT: dict[str, Any] = {
    "suffix": " €",
    "thousand_separator": ".",
    "decimal_separator": ",",
    "decimal_scale": 0,
    "allow_negative": False,
    "allow_decimal": False,
    "min": 0,
    "max": MAX_PRICE,
    "clamp_behavior": "strict",
    "hide_controls": True,
    "size": "xs",
    "w": 130,
}

_PERCENT_INPUT: dict[str, Any] = {
    "min": 0,
    "max": MAX_CONTRIBUTION_MARGIN_PERCENT,
    "step": 1,
    "suffix": " %",
    "decimal_scale": 0,
    "allow_negative": False,
    "allow_decimal": False,
    "clamp_behavior": "strict",
    "w": 200,
    "on_blur": DailyRateState.save_margins,
    "key": DailyRateState.form_version.to_string(),
}


def margin_settings() -> rx.Component:
    """Card with the two margins shared by all roles."""
    return mn.box(
        mn.group(
            mn.number_input(
                label=f"{MIN_MARGIN_LABEL} (Empf. VK)",
                default_value=DailyRateState.min_margin,
                on_change=DailyRateState.set_min_margin_draft,
                **_PERCENT_INPUT,
            ),
            mn.number_input(
                label=f"{MARGIN_LABEL} ({LIST_LABEL})",
                default_value=DailyRateState.margin,
                on_change=DailyRateState.set_margin_draft,
                **_PERCENT_INPUT,
            ),
            mn.text(
                PRICE_HINT,
                size="sm",
                c=theme.TEXT_MUTED,
                style={"flex": "1 1 260px"},
            ),
            align="flex-end",
            gap="md",
        ),
        style=theme.CARD,
        p="md",
        w="100%",
        max_width="1200px",
    )


def _margin_text(
    margin: rx.Var, share: rx.Var, manual: rx.Var | bool = False
) -> rx.Component:
    """Small "DB 340 € · 30 %" text next to a price."""
    return mn.text(
        rx.cond(
            margin,
            rx.fragment(
                rx.cond(manual, "manuell · ", ""),
                "DB ",
                de_number(margin, decimal_scale=0, suffix=" €"),
                " · ",
                share.to_string(),
                " %",
            ),
            "",
        ),
        size="xs",
        c=theme.TEXT_MUTED,
        style={"whiteSpace": "nowrap"},
    )


def _price_input(
    value: rx.Var, on_blur: Callable[[rx.Var], Any], key: rx.Var
) -> rx.Component:
    """Editable euro amount; a new key reloads its value."""
    return mn.number_input(
        default_value=value,
        on_blur=on_blur,
        key=key,
        **_CURRENCY_INPUT,
    )


def _price_cell(price: rx.Component, info: rx.Component | None = None) -> rx.Component:
    return mn.table.td(
        mn.group(price, info, gap="sm", wrap="nowrap", align="center")
        if info is not None
        else price
    )


def daily_rates_table_row(rate: ObjectVar[DailyRate]) -> rx.Component:
    """One role with its cost, recommended sales price and list price."""
    role_id = rate.role_id
    key = (
        role_id.to_string()
        + "-"
        + DailyRateState.form_version.to_string()
        + "-"
        + rate.production_cost.to_string()
    )
    return mn.table.tr(
        mn.table.td(
            mn.text(rate.role_name, size="sm", fw="500", style={"whiteSpace": "nowrap"})
        ),
        _price_cell(
            _price_input(
                rate.production_cost,
                lambda value: DailyRateState.save_production_cost(role_id, value),
                key + "-cost",
            )
        ),
        _price_cell(
            mn.number_input(
                value=rx.cond(rate.recommended_price, rate.recommended_price, ""),
                read_only=True,
                variant="filled",
                custom_attrs={"tabIndex": -1},
                **_CURRENCY_INPUT,
            ),
            _margin_text(rate.recommended_margin, rate.recommended_share),
        ),
        _price_cell(
            _price_input(
                rate.effective_list_price,
                lambda value: DailyRateState.save_list_price(role_id, value),
                key
                + "-list-"
                + rate.list_price.to_string()
                + "-"
                + DailyRateState.margin_draft.to_string(),
            ),
            _margin_text(rate.list_margin, rate.list_share, rate.list_price),
        ),
    )


def _message_row(content: rx.Component) -> rx.Component:
    return mn.table.tr(
        mn.table.td(content, col_span=len(COLUMN_LABELS), style={"textAlign": "center"})
    )


def daily_rates_table() -> rx.Component:
    """Table with one row of price inputs per role."""
    return mn.table(
        mn.table.thead(
            mn.table.tr(
                *(
                    mn.table.th(mn.text(label, size="sm", fw="700"))
                    for label in COLUMN_LABELS
                ),
                style=sticky_header_style,
            ),
        ),
        mn.table.tbody(
            rx.cond(
                DailyRateState.is_loading,
                _message_row(
                    rx.hstack(
                        rx.spinner(size="3"),
                        mn.text("Lade Tagessätze...", size="sm"),
                        align="center",
                        justify="center",
                        spacing="3",
                    )
                ),
                rx.cond(
                    DailyRateState.rows.length() > 0,
                    rx.foreach(DailyRateState.rows, daily_rates_table_row),
                    _message_row(mn.text(EMPTY_TEXT, size="sm", c="dimmed")),
                ),
            )
        ),
        sticky_header=True,
        sticky_header_offset="0px",
        striped=False,
        highlight_on_hover=True,
        highlight_on_hover_color=rx.color_mode_cond(
            light="gray.0",
            dark="dark.8",
        ),
        vertical_spacing="xs",
        w="100%",
    )


def daily_rates_toolbar() -> list[rx.Component]:
    """Toolbar actions of the daily rates page."""
    return [
        toolbar_search(
            DailyRateState.search_filter,
            DailyRateState.set_search_filter,
            "Rollen suchen",
        ),
    ]
