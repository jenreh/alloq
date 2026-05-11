import reflex as rx

import appkit_mantine as mn
from alloq_commons.components.formatters import format_date_de
from alloq_commons.components.forms import section
from alloq_commons.components.modal_layout import (
    MODAL_CLASS,
    modal_footer,
    modal_form_layout,
)
from alloq_commons.models.public_holiday import PublicHoliday
from alloq_commons.states.holiday_state import HolidayState
from appkit_ui.components.dialogs import delete_dialog
from appkit_ui.components.form_inputs import hidden_field
from appkit_ui.styles import sticky_header_style


def holiday_form_fields(holiday: PublicHoliday | None = None) -> rx.Component:
    """Reusable form fields for holiday add/edit dialogs."""
    is_edit_mode = holiday is not None

    return mn.flex(
        hidden_field(
            name="holiday_id",
            default_value=(
                holiday.id.to_string() if is_edit_mode else ""  # type: ignore[union-attr]
            ),
        ),
        section(
            mn.text_input(
                name="name",
                label="Name",
                description="Bezeichnung des Feiertags (z.B. Ostermontag).",
                default_value=holiday.name if is_edit_mode else "",
                required=True,
                max_length=255,
            ),
            mn.date_picker_input(
                name="date",
                label="Datum",
                description="Datum des Feiertags.",
                left_section=rx.icon("calendar-days", size=16),
                **(
                    {"default_value": HolidayState.selected_holiday_date_iso}
                    if is_edit_mode
                    else {}
                ),
                required=True,
                value_format="DD.MM.YYYY",
                clearable=False,
            ),
        ),
        section(
            mn.switch(
                name="is_recurring",
                label="Jährlich wiederkehrend (fixer Termin)",
                description=(
                    "Aktivieren für Feiertage mit festem Datum"
                    " (z.B. Neujahr am 1. Januar)."
                ),
                default_checked=holiday.is_recurring if is_edit_mode else False,
            ),
        ),
        direction="column",
        gap="md",
        width="100%",
    )


def _holiday_modal(
    title: str,
    opened: bool | rx.Var,
    on_close: rx.EventHandler,
    on_submit: rx.EventHandler,
    submit_label: str,
    content: rx.Component,
) -> rx.Component:
    """Shared modal structure for add/edit holiday."""
    return mn.modal(
        modal_form_layout(
            content=mn.flex(
                content,
                mn.space(height="2rem"),
                direction="column",
                width="100%",
            ),
            footer=modal_footer(
                submit_label,
                on_close,
                loading=HolidayState.is_loading,
            ),
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


def add_holiday_modal() -> rx.Component:
    """Modal for adding a new holiday."""
    return _holiday_modal(
        title="Feiertag hinzufügen",
        opened=HolidayState.add_modal_open,
        on_close=HolidayState.close_add_modal,
        on_submit=HolidayState.create_holiday,
        submit_label="Feiertag speichern",
        content=holiday_form_fields(),
    )


def edit_holiday_modal() -> rx.Component:
    """Modal for editing an existing holiday."""
    return _holiday_modal(
        title="Feiertag bearbeiten",
        opened=HolidayState.edit_modal_open,
        on_close=HolidayState.close_edit_modal,
        on_submit=HolidayState.update_holiday,
        submit_label="Feiertag aktualisieren",
        content=holiday_form_fields(holiday=HolidayState.selected_holiday),
    )


def add_holiday_button() -> rx.Component:
    """Button to open the add holiday modal."""
    return mn.action_icon(
        rx.icon("plus", size=20),
        variant="filled",
        auto_contrast=True,
        size="lg",
        radius="md",
        on_click=HolidayState.open_add_modal,
    )


def holiday_search_input() -> rx.Component:
    """Search input for filtering holidays by name."""
    return mn.text_input(
        placeholder="Feiertage suchen...",
        left_section=rx.icon("search", size=16),
        left_section_pointer_events="none",
        value=HolidayState.search_filter,
        on_change=HolidayState.set_search_filter,
        size="sm",
        w="16rem",
    )


def holiday_year_select() -> rx.Component:
    """Year selection for filtering holidays."""
    return mn.select(
        data=HolidayState.available_years,
        value=HolidayState.selected_year_str,
        on_change=HolidayState.change_year,
        allow_deselect=False,
        size="sm",
        w="8rem",
        key=rx.State.router.page.path,
    )


def _update_holiday_button(holiday: PublicHoliday) -> rx.Component:
    return rx.icon_button(
        rx.icon("square-pen", size=16),
        on_click=lambda: HolidayState.select_holiday_and_open_edit(holiday.id),
        variant="ghost",
    )


def _delete_holiday_button(holiday: PublicHoliday) -> rx.Component:
    return delete_dialog(
        title="Löschen bestätigen",
        content=rx.cond(holiday.name, holiday.name, "Unbekannter Feiertag"),
        on_click=lambda: HolidayState.delete_holiday(holiday.id),
        icon_button=True,
        color="red",
        variant="subtle",
    )


def holidays_table_row(holiday: PublicHoliday) -> rx.Component:
    """Render a single holiday as a table row."""
    _parts = holiday.date.to(str).split("-")
    _day_month = _parts[2] + "." + _parts[1] + "."
    return mn.table.tr(
        mn.table.td(
            mn.text(
                format_date_de(holiday.date),
                size="sm",
                fw="500",
                style={"whiteSpace": "nowrap"},
            ),
        ),
        mn.table.td(
            mn.text(holiday.name, size="sm"),
        ),
        mn.table.td(
            rx.cond(
                holiday.is_recurring,
                mn.badge("Jährlich", color="teal", variant="light", size="sm"),
                mn.badge("Beweglich", color="orange", variant="light", size="sm"),
            ),
            style={"textAlign": "center"},
        ),
        mn.table.td(
            mn.group(
                _update_holiday_button(holiday),
                _delete_holiday_button(holiday),
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
                mn.text("Lade Feiertage...", size="sm"),
                align="center",
                justify="center",
                spacing="3",
            ),
            col_span=4,
            style={"textAlign": "center"},
        ),
    )


def holidays_table() -> rx.Component:
    """Full CRUD interface for public holidays."""
    return mn.stack(
        add_holiday_modal(),
        edit_holiday_modal(),
        mn.table(
            mn.table.thead(
                mn.table.tr(
                    mn.table.th(mn.text("Datum", size="sm", fw="700")),
                    mn.table.th(mn.text("Name", size="sm", fw="700")),
                    mn.table.th(
                        mn.text("Typ", size="sm", fw="700"),
                        style={"textAlign": "center"},
                    ),
                    mn.table.th(mn.text("", size="sm")),
                    style=sticky_header_style,
                ),
            ),
            mn.table.tbody(
                rx.cond(
                    HolidayState.is_loading,
                    _loading_row(),
                    rx.foreach(
                        HolidayState.filtered_holidays,
                        holidays_table_row,
                    ),
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


def holidays_toolbar() -> rx.Component:
    """Top-right holiday page toolbar."""
    return rx.flex(
        holiday_search_input(),
        holiday_year_select(),
        add_holiday_button(),
        width="auto",
        gap="12px",
        align="center",
        justify="end",
        style={
            "position": "fixed",
            "top": "2.25rem",
            "right": "2rem",
            "z_index": "20",
        },
    )
