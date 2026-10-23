"""Excel-style price sheets using the shared planning-grid controller.

Every signed-in user reads the price lists; only admins edit them.
"""

from typing import Any

import reflex as rx
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_commons import theme
from alloq_commons.components.excel_grid import (
    excel_grid,
    grid_cell_attrs,
    grid_row_attrs,
)
from alloq_commons.components.toolbar import icon_button, primary_button
from alloq_commons.models.price_list import PriceGridRow
from alloq_commons.state.price_list_state import PriceListState as S
from appkit_user.authentication.components.components import requires_admin
from appkit_user.authentication.states import UserSession

COLUMNS = [
    ("la", "LA", "", 64),
    ("label", "Rolle", "", 220),
    ("hourly_cost", "Stundensatz", "HK", 120),
    ("daily_cost", "Tagessatz", "HK", 120),
    ("minimum_daily", "Tagessatz", "inkl. DB · Mindest-VK", 140),
    ("minimum_hourly", "Stundensatz", "Mindest-VK", 120),
    ("sales_price", "Tagessatz", "VK", 120),
    ("hourly_sales", "Stundensatz", "VK", 120),
]
COLUMN_WIDTHS = {column: width for column, _, _, width in COLUMNS}
CAN_EDIT_PRICES = UserSession.user.is_admin
"""Frontend Var: the admin switch opens the price lists for editing."""
ROLE_COLUMN_WIDTH = 190
ACTION_COLUMN_WIDTH = 84
CELL_STYLE = {
    "border": "1px solid var(--alloq-border)",
    "height": "28px",
    "padding": "2px 6px",
    "fontVariantNumeric": "tabular-nums",
    "whiteSpace": "nowrap",
    "position": "relative",
    "userSelect": "none",
}
SHEET_CSS = """
#price-list-grid th, #price-comparison-grid th {
  background-color: var(--alloq-surface-muted);
  text-align: right;
  padding: 6px;
}
#price-list-grid th:nth-child(-n+2),
#price-comparison-grid th:nth-child(-n+2) { text-align: left; }
#price-list-grid td, #price-comparison-grid td {
  padding: 2px 6px;
  height: 28px;
  font-size: 12px;
  line-height: 1.25;
}
#price-list-grid td .mantine-Select-input {
  height: 22px;
  min-height: 22px;
  font-size: 12px;
  line-height: 20px;
  padding-top: 0;
  padding-bottom: 0;
}
#price-list-grid td[data-calculated="false"],
#price-comparison-grid td[data-calculated="false"] {
  background: var(--alloq-surface-solid);
}
#price-list-grid td[data-calculated="true"],
#price-comparison-grid td[data-calculated="true"] {
  background: color-mix(in srgb, var(--mantine-color-blue-6) 6%,
    var(--alloq-surface-solid));
}
"""


def _visible(column: str, component: rx.Component) -> rx.Component:
    if column == "hourly_cost":
        return rx.cond(S.hourly_visible, component, rx.fragment())
    return component


def _sticky(column: str) -> dict[str, Any]:
    if column in {"la", "label"}:
        return {
            "position": "sticky",
            "left": "0px" if column == "la" else f"{COLUMN_WIDTHS['la']}px",
            "zIndex": 3,
            "boxShadow": "inset -1px 0 0 var(--alloq-border)",
        }
    return {}


def _pinned_right(background: str, z_index: int) -> dict[str, Any]:
    return {
        "position": "sticky",
        "right": "0px",
        "zIndex": z_index,
        "boxShadow": "inset 1px 0 0 var(--alloq-border)",
        "backgroundColor": background,
    }


def _cell(
    row: ObjectVar[PriceGridRow], column: str, width: int, comparison: bool
) -> rx.Component:
    text = column in {"la", "label"}
    editable: Any = text or column == "sales_price"
    if column in {"hourly_cost", "daily_cost"}:
        basis = S.compare_cost_basis if comparison else S.cost_basis
        editable = basis == ("hour" if column == "hourly_cost" else "day")
    calculated = rx.cond(editable, "false", "true")
    if comparison:
        editable = False
    attrs = grid_cell_attrs(
        row.key.to(str) + "|" + column,
        column,
        row.cell_values.to(dict[str, str])[column],
    )
    attrs.update(
        {
            "data-cell-type": "text" if text else "decimal",
            "data-read-only": rx.cond(editable, "false", "true"),
            "data-calculated": calculated,
            "data-max-length": 50 if column == "la" else 255,
            "aria-readonly": rx.cond(editable, "false", "true"),
        }
    )
    if column in {"la", "label"}:
        attrs["data-grid-frozen"] = "true"
    warning = row.below_minimum if column == "sales_price" else False
    if column == "sales_price":
        attrs["data-copy-value"] = row.effective_sales
    attrs["data-below-minimum"] = rx.cond(warning, "true", "false")
    return _visible(
        column,
        mn.table.td(
            row.display.to(dict[str, str])[column],
            p="2px 6px",
            ta="left" if text else "right",
            custom_attrs=attrs,
            title=rx.cond(
                warning,
                "Angebots-VK liegt unter dem Mindest-VK",
                rx.cond(
                    editable,
                    "Eingabe · Doppelklick oder direkt tippen",
                    "Berechnet · schreibgeschützt",
                ),
            ),
            style={
                **CELL_STYLE,
                **_sticky(column),
                "minWidth": f"{width}px",
                "width": f"{width}px",
                "maxWidth": f"{width}px",
                "textAlign": "left" if text else "right",
                "overflow": "hidden",
                "textOverflow": "ellipsis",
                "backgroundColor": "var(--alloq-surface-solid)",
                "color": rx.cond(
                    warning, "var(--mantine-color-yellow-light-color)", theme.TEXT
                ),
            },
        ),
    )


def _row(row: ObjectVar[PriceGridRow], comparison: bool = False) -> rx.Component:
    cells = [_cell(row, column, width, comparison) for column, _, _, width in COLUMNS]
    if not comparison:
        cells.extend(
            [
                rx.cond(
                    S.show_roles,
                    mn.table.td(
                        mn.select(
                            data=S.role_options.to(list),
                            value=row.role_id,
                            clearable=True,
                            placeholder="Keine Verknüpfung",
                            size="xs",
                            w="100%",
                            on_change=lambda value: S.set_role(row.key, value),  # ty: ignore[invalid-argument-type]
                            disabled=S.is_saving | ~CAN_EDIT_PRICES,
                        )
                    ),
                    rx.fragment(),
                ),
                mn.table.td(
                    requires_admin(
                        mn.group(
                            mn.action_icon(
                                rx.icon("arrow-up", size=14),
                                title="Zeile nach oben",
                                variant="subtle",
                                size="xs",
                                aria_label="Zeile nach oben",
                                on_click=S.move_row(row.key, -1),
                            ),
                            mn.action_icon(
                                rx.icon("arrow-down", size=14),
                                title="Zeile nach unten",
                                variant="subtle",
                                size="xs",
                                aria_label="Zeile nach unten",
                                on_click=S.move_row(row.key, 1),
                            ),
                            mn.action_icon(
                                rx.icon("trash-2", size=14),
                                title="Zeile löschen",
                                variant="subtle",
                                size="xs",
                                aria_label="Zeile löschen",
                                color="red",
                                on_click=S.delete_row(row.key),
                            ),
                            gap=0,
                            wrap="nowrap",
                        )
                    ),
                    p="4px",
                    style={
                        "whiteSpace": "nowrap",
                        **_pinned_right("var(--alloq-surface-solid)", 3),
                    },
                ),
            ]
        )
    return mn.table.tr(
        *cells, key=row.key, custom_attrs=grid_row_attrs(row.key, "rates")
    )


def price_sheet(comparison: bool = False) -> rx.Component:
    columns = [
        _visible(column, rx.el.col(style={"width": f"{width}px"}))
        for column, _, _, width in COLUMNS
    ]
    base_width = sum(
        width for column, _, _, width in COLUMNS if column != "hourly_cost"
    )
    table_width = rx.Var.create(base_width) + rx.cond(
        S.hourly_visible, COLUMN_WIDTHS["hourly_cost"], 0
    ).to(int)
    headers = []
    for column, title, subtitle, width in COLUMNS:
        headers.append(
            _visible(
                column,
                mn.table.th(
                    mn.text(title, fw="600", size="sm"),
                    mn.text(subtitle or "\u00a0", fw="500", size="xs"),
                    bg=theme.SURFACE_MUTED,
                    ta="left" if column in {"la", "label"} else "right",
                    style={
                        **CELL_STYLE,
                        **_sticky(column),
                        "minWidth": f"{width}px",
                        "width": f"{width}px",
                        "backgroundColor": "var(--alloq-surface-muted)",
                        "zIndex": 6 if column in {"la", "label"} else 5,
                        "textAlign": "left" if column in {"la", "label"} else "right",
                    },
                ),
            )
        )
    if not comparison:
        columns.extend(
            [
                rx.cond(
                    S.show_roles,
                    rx.el.col(style={"width": f"{ROLE_COLUMN_WIDTH}px"}),
                    rx.fragment(),
                ),
                rx.el.col(style={"width": f"{ACTION_COLUMN_WIDTH}px"}),
            ]
        )
        table_width += ACTION_COLUMN_WIDTH + rx.cond(
            S.show_roles, ROLE_COLUMN_WIDTH, 0
        ).to(int)
        headers.extend(
            [
                rx.cond(S.show_roles, mn.table.th("Planungsrolle"), rx.fragment()),
                mn.table.th(
                    "",
                    style={
                        "width": f"{ACTION_COLUMN_WIDTH}px",
                        **_pinned_right("var(--alloq-surface-muted)", 6),
                    },
                ),
            ]
        )
    table = mn.table(
        rx.el.colgroup(*columns),
        mn.table.thead(
            mn.table.tr(*headers), custom_attrs={"data-grid-header": "true"}
        ),
        mn.table.tbody(
            rx.foreach(
                S.compare_rows if comparison else S.rows,
                lambda row: _row(row, comparison),
            )
        ),
        sticky_header=True,
        with_column_borders=True,
        with_table_border=True,
        horizontal_spacing="xs",
        vertical_spacing="xs",
        style={
            "borderCollapse": "separate",
            "borderSpacing": 0,
            "tableLayout": "fixed",
            "width": table_width.to_string() + "px",
            "minWidth": table_width.to_string() + "px",
            "maxWidth": table_width.to_string() + "px",
        },
    )
    return excel_grid(
        table,
        id="price-comparison-grid" if comparison else "price-list-grid",
        grid_label="Preislistenvergleich" if comparison else "Tagessatzkalkulation",
        revision=S.grid_revision,
        dirty=False if comparison else S.has_dirty,
        saving=S.is_saving,
        read_only=True if comparison else S.is_saving | ~CAN_EDIT_PRICES,
        decimals=2,
        max_value=100_000,
        on_commit=S.apply_cell_changes,
        on_reject=S.notify_rejected,
        on_save=S.save,
        on_discard=S.discard,
        navigation_guard=not comparison,
        style={
            "overflow": "auto",
            "maxHeight": "55vh",
            "width": "100%",
            "outline": "none",
            "--grid-editor-font-size": "12px",
        },
    )


def _setting(field: str, label: str, width: int) -> rx.Component:
    return mn.text_input(
        label=label,
        default_value=S.settings_values[field],
        size="xs",
        w=width,
        key=S.settings_revision.to_string() + field,
        on_blur=lambda value: S.set_setting(field, value),  # ty: ignore[invalid-argument-type]
        disabled=S.is_saving,
    )


def _list_select(on_change: Any) -> rx.Component:
    return mn.select(
        placeholder="Preisliste auswählen",
        data=S.list_options,
        value=S.selected_id,
        on_change=on_change,
        allow_deselect=False,
        w=260,
        size="xs",
        custom_attrs={"aria-label": "Preisliste"},
    )


def price_list_toolbar() -> list[rx.Component]:
    """List switch for everyone; admins switch with the unsaved-draft check."""
    return [
        requires_admin(
            _list_select(lambda value: S.request_action("select", value)),  # ty: ignore[invalid-argument-type]
            fallback=_list_select(S.open_list),
        ),
        requires_admin(*edit_actions()),
    ]


def edit_actions() -> list[rx.Component]:
    """Toolbar actions that change or save price lists."""
    return [
        icon_button("copy", "Duplizieren", S.request_action("duplicate", "")),
        icon_button(
            rx.cond(S.is_archived, "archive-restore", "archive"),
            rx.cond(S.is_archived, "Wiederherstellen", "Archivieren"),
            S.toggle_archive,
        ),
        icon_button("refresh-cw", "Neu laden", S.request_action("reload", "")),
        icon_button(
            "undo-2",
            "Verwerfen",
            S.discard,
            disabled=~S.has_dirty | S.is_saving,
        ),
        icon_button(
            "save",
            "Speichern",
            S.save,
            loading=S.is_saving,
            disabled=~S.has_dirty,
        ),
        primary_button("Neu", "plus", S.request_action("new", "")),
    ]


def _settings() -> rx.Component:
    """List settings; the fieldset disables them for readers."""
    return rx.el.fieldset(
        mn.group(
            _setting("name", "Name", 240),
            mn.date_input(
                label="Stand",
                value=S.settings_values["as_of"],
                value_format="DD.MM.YYYY",
                clearable=True,
                size="xs",
                w=150,
                on_change=lambda value: S.set_setting("as_of", value),  # ty: ignore[invalid-argument-type]
            ),
            mn.select(
                label="HK-Eingabe",
                data=[
                    {"value": "day", "label": "Pro Tag"},
                    {"value": "hour", "label": "Pro Stunde"},
                ],
                value=S.cost_basis,
                on_change=lambda value: S.set_setting("cost_basis", value),  # ty: ignore[invalid-argument-type]
                size="xs",
                w=140,
                allow_deselect=False,
            ),
            _setting("hours_per_day", "Stunden / Tag", 110),
            _setting("minimum_margin", "Mindest-DB (%)", 120),
            rx.cond(
                S.settings_values["target_margin"] != "",
                _setting("target_margin", "Ziel-DB (%) · Bestand", 170),
                rx.fragment(),
            ),
            gap="sm",
            align="flex-end",
            wrap="wrap",
        ),
        disabled=~CAN_EDIT_PRICES,
        style={"display": "contents"},
    )


def _view_options() -> rx.Component:
    return mn.group(
        *[
            mn.checkbox(
                label=label,
                checked=getattr(S, field),
                size="xs",
                on_change=lambda value, field=field: S.set_view(field, value),  # ty: ignore[invalid-argument-type]
            )
            for field, label in [
                ("show_hourly", "HK pro Stunde"),
                ("show_roles", "Planungsrollen"),
                ("show_archived", "Archivierte Preislisten"),
            ]
        ],
        mn.select(
            placeholder="Mit Preisliste vergleichen",
            data=S.list_options,
            value=S.compare_id,
            clearable=True,
            on_change=S.set_compare,
            size="xs",
            w=260,
        ),
        gap="md",
        wrap="wrap",
    )


def _switch_dialog() -> rx.Component:
    return mn.modal(
        mn.text("Die Preisliste enthält ungespeicherte Änderungen.", size="sm"),
        mn.group(
            mn.button("Bleiben", variant="default", on_click=S.resolve_pending("stay")),
            mn.button(
                "Verwerfen",
                color="red",
                variant="light",
                on_click=S.resolve_pending("discard"),
            ),
            mn.button(
                "Speichern & wechseln",
                on_click=S.resolve_pending("save"),
                loading=S.is_saving,
            ),
            justify="flex-end",
            mt="md",
        ),
        title="Ungespeicherte Änderungen",
        opened=S.pending_action != "",
        on_close=S.resolve_pending("stay"),
        centered=True,
    )


def price_list_editor() -> rx.Component:
    return mn.stack(
        rx.el.style(SHEET_CSS),
        _settings(),
        _view_options(),
        rx.cond(
            S.error_message != "",
            mn.text(S.error_message, c="red", size="sm"),
            rx.fragment(),
        ),
        mn.group(
            mn.text(
                "HK ÷ (1 - Mindest-DB), auf volle Euro aufgerundet. "
                "Weiß = Eingabe, Hellblau = berechnet. VK = Angebotspreis.",
                size="xs",
                c=theme.TEXT_MUTED,
            ),
            rx.cond(
                S.has_dirty,
                mn.badge("Ungespeicherte Änderungen", variant="light"),
                rx.fragment(),
            ),
            justify="space-between",
        ),
        price_sheet(),
        requires_admin(
            mn.group(
                mn.button(
                    "Zeile hinzufügen",
                    left_section=rx.icon("plus", size=14),
                    size="xs",
                    on_click=S.add_row,
                ),
                justify="space-between",
            )
        ),
        rx.cond(
            S.compare_id != "",
            mn.stack(
                mn.text(S.compare_name, fw="600"),
                price_sheet(comparison=True),
                gap="xs",
            ),
            rx.fragment(),
        ),
        _switch_dialog(),
        gap="md",
        w="100%",
    )
