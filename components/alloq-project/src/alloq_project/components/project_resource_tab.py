import reflex as rx
from alloq_commons.components.formatters import de_number, format_date_de
from alloq_commons.components.forms import section
from alloq_project.states.project_resource_state import (
    MAX_DAYS_PER_WEEK,
    MIN_DAYS_PER_WEEK,
    ProjectResourceState,
)

import appkit_mantine as mn
from appkit_ui.components.dialogs import delete_dialog

_ROW_STYLE = {
    "padding": "6px 12px",
    "borderRadius": "6px",
    "backgroundColor": "var(--alloq-item-bg, var(--alloq-surface-muted))",
}


def _section_title(title: str | rx.Var, count: rx.Var | None = None) -> rx.Component:
    badge = (
        mn.badge(count.to_string(), variant="light", radius="sm", size="sm")
        if count is not None
        else rx.fragment()
    )
    return mn.group(
        mn.text(title, size="sm", fw="700", c="dimmed"),
        badge,
        gap="xs",
        align="center",
    )


def _empty(text: str) -> rx.Component:
    return mn.text(text, size="sm", c="dimmed", ta="center", py="sm")


def _period_row(period: rx.Var) -> rx.Component:
    """One planned period with edit and delete actions."""
    is_editing = ProjectResourceState.editing_key == period.key
    return mn.group(
        mn.text(
            period.employee_name,
            size="sm",
            fw="600",
            truncate=True,
            style={"flex": "1", "minWidth": "0"},
        ),
        mn.badge(period.role_name, variant="light", color="teal", radius="sm"),
        mn.text(
            format_date_de(period.start) + " \u2013 " + format_date_de(period.end),
            size="xs",
            c="dimmed",
            style={"whiteSpace": "nowrap"},
        ),
        mn.badge(
            de_number(period.days_per_week, decimal_scale=1, suffix=" T/Wo"),
            variant="light",
            color="blue",
            radius="sm",
            style={"flexShrink": "0"},
        ),
        de_number(
            period.total_pt,
            decimal_scale=1,
            suffix=" PT",
            style={"fontSize": "0.75rem", "width": "4rem", "textAlign": "right"},
        ),
        mn.tooltip(
            mn.action_icon(
                rx.icon("square-pen", size=14),
                variant="subtle",
                size="sm",
                on_click=ProjectResourceState.edit_period(period.key),
            ),
            label="Zeitraum bearbeiten",
        ),
        delete_dialog(
            title="Zeitraum löschen",
            content=period.employee_name + " (" + period.role_name + ")",
            on_click=ProjectResourceState.delete_period(period.key),
            icon_button=True,
            color="red",
            size="sm",
            variant="subtle",
        ),
        w="100%",
        gap="sm",
        align="center",
        wrap="nowrap",
        style={
            **_ROW_STYLE,
            "outline": rx.cond(
                is_editing, "2px solid var(--mantine-color-teal-5)", "none"
            ),
        },
    )


def _planned_section() -> rx.Component:
    return section(
        _section_title("Geplante Ressourcen", ProjectResourceState.periods.length()),
        rx.cond(
            ProjectResourceState.periods.length() > 0,
            mn.stack(
                rx.foreach(ProjectResourceState.periods, _period_row),
                gap="4px",
                w="100%",
            ),
            _empty("Noch keine Ressourcen geplant."),
        ),
    )


def _plan_fields() -> rx.Component:
    return mn.simple_grid(
        mn.select(
            label="Rolle",
            data=ProjectResourceState.role_options,
            value=ProjectResourceState.role_id,
            on_change=ProjectResourceState.set_role_id,
            searchable=True,
            allow_deselect=False,
            size="sm",
        ),
        mn.date_input(
            label="Von",
            value=ProjectResourceState.start_iso,
            on_change=ProjectResourceState.set_start,
            min_date=ProjectResourceState.project_start,
            max_date=ProjectResourceState.project_end,
            size="sm",
            locale="de",
            value_format="DD.MM.YYYY",
            clearable=False,
            left_section=rx.icon("calendar", size=16),
        ),
        mn.date_input(
            label="Bis",
            value=ProjectResourceState.end_iso,
            on_change=ProjectResourceState.set_end,
            min_date=ProjectResourceState.project_start,
            max_date=ProjectResourceState.project_end,
            size="sm",
            locale="de",
            value_format="DD.MM.YYYY",
            clearable=False,
            left_section=rx.icon("calendar", size=16),
        ),
        mn.number_input(
            label="Tage pro Woche",
            default_value=ProjectResourceState.days_per_week,
            on_change=ProjectResourceState.set_days_per_week,
            min=MIN_DAYS_PER_WEEK,
            max=MAX_DAYS_PER_WEEK,
            step=0.5,
            decimal_scale=1,
            decimal_separator=",",
            size="sm",
            key=ProjectResourceState.form_version.to_string(),
        ),
        cols=4,
        spacing="sm",
        w="100%",
    )


def _candidate_row(candidate: rx.Var) -> rx.Component:
    """One employee who can be planned with the current form values."""
    return mn.group(
        mn.stack(
            mn.text(candidate.name, size="sm", fw="600", truncate=True),
            mn.text(candidate.seniority, size="xs", c="dimmed"),
            gap="0",
            style={"flex": "1", "minWidth": "0"},
        ),
        rx.cond(
            candidate.already_planned,
            mn.badge("geplant", variant="light", color="teal", radius="sm"),
            rx.fragment(),
        ),
        rx.cond(
            candidate.conflict_weeks > 0,
            mn.badge(
                candidate.conflict_weeks.to_string() + " Wochen knapp",
                variant="light",
                color="orange",
                radius="sm",
            ),
            rx.fragment(),
        ),
        de_number(
            candidate.avg_free_days,
            decimal_scale=1,
            prefix="Ø ",
            suffix=" T/Wo frei",
            style={"fontSize": "0.75rem", "whiteSpace": "nowrap"},
        ),
        mn.button(
            rx.cond(ProjectResourceState.is_editing, "Übernehmen", "Einplanen"),
            size="xs",
            variant="light",
            left_section=rx.icon("user-plus", size=14),
            loading=ProjectResourceState.is_saving,
            disabled=ProjectResourceState.form_error != "",
            on_click=ProjectResourceState.assign(candidate.employee_id),
        ),
        w="100%",
        gap="sm",
        align="center",
        wrap="nowrap",
        style=_ROW_STYLE,
    )


def _plan_section() -> rx.Component:
    return section(
        mn.group(
            _section_title(
                rx.cond(
                    ProjectResourceState.is_editing,
                    "Zeitraum bearbeiten",
                    "Ressource planen",
                ),
            ),
            rx.cond(
                ProjectResourceState.is_editing,
                mn.button(
                    "Abbrechen",
                    size="xs",
                    variant="subtle",
                    color="gray",
                    on_click=ProjectResourceState.cancel_edit,
                ),
                rx.fragment(),
            ),
            justify="space-between",
            align="center",
            w="100%",
        ),
        _plan_fields(),
        rx.cond(
            ProjectResourceState.form_error != "",
            mn.text(ProjectResourceState.form_error, size="xs", c="red"),
            rx.fragment(),
        ),
        _section_title("Verfügbare Personen", ProjectResourceState.candidates.length()),
        rx.cond(
            ProjectResourceState.candidates.length() > 0,
            mn.stack(
                rx.foreach(ProjectResourceState.candidates, _candidate_row),
                gap="4px",
                w="100%",
            ),
            _empty("Keine verfügbaren Personen für diese Rolle im Zeitraum."),
        ),
    )


def ressourcen_tab() -> rx.Component:
    """Ressourcen tab: planned periods and a simple planning form."""
    return mn.stack(
        rx.cond(
            ProjectResourceState.is_loading,
            mn.center(mn.loader(size="sm"), py="xl"),
            mn.stack(
                _planned_section(),
                _plan_section(),
                gap="md",
                w="100%",
            ),
        ),
        mn.space(h="2rem"),
        gap="md",
        w="100%",
        class_name="alloq-modal-scroll",
        on_mount=ProjectResourceState.load_selected,
    )
