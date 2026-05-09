import reflex as rx
from alloq_commons.components import de_number
from alloq_commons.components.formatters import format_date_de
from alloq_commons.components.forms import section
from alloq_project.states.project_state import ProjectState

import appkit_mantine as mn


def _summary_cell(
    label: str,
    value: rx.Var | float,
    *,
    color: str | None = None,
) -> rx.Component:
    """One stat block within the EV summary row."""
    return mn.stack(
        mn.text(label, size="xs", c="dimmed", fw="500"),
        de_number(
            value,
            decimal_scale=2,
            fixed_decimal_scale=True,
            suffix=" €",
            style={
                "fontSize": "0.875rem",
                "fontWeight": "700",
                **({"color": f"var(--mantine-color-{color}-6)"} if color else {}),
            },
        ),
        gap="2px",
    )


def _ev_summary() -> rx.Component:
    """Row of final EV figures (BAC/EV/AC) and EAC forecasts."""
    summary = ProjectState.ev_summary
    return rx.cond(
        summary.has_data,
        mn.simple_grid(
            _summary_cell("Budget", summary.budget),
            _summary_cell("Fertigstellungswert", summary.earned_value),
            _summary_cell("Ist-Kosten", summary.actual_cost),
            _summary_cell("Prognose linear", summary.eac_linear, color="teal"),
            _summary_cell("Prognose additiv", summary.eac_additive, color="violet"),
            cols=5,
            spacing="md",
            w="100%",
            style={
                "borderTop": "1px solid var(--alloq-border)",
                "paddingTop": "12px",
                "marginTop": "8px",
            },
        ),
        rx.fragment(),
    )


def _ev_chart() -> rx.Component:
    """Line chart showing PV, EV, AC and two forecast lines."""
    return rx.cond(
        ProjectState.ev_chart_data.length() > 1,
        mn.line_chart(
            data=ProjectState.ev_chart_data,
            data_key="label",
            series=[
                {"name": "Planned Value", "color": "var(--mantine-color-gray-5)"},
                {"name": "Earned Value", "color": "var(--mantine-color-blue-6)"},
                {"name": "Actual Cost", "color": "var(--mantine-color-orange-6)"},
                {
                    "name": "Prognose (linear)",
                    "color": "var(--mantine-color-teal-5)",
                    "strokeDasharray": "4 4",
                },
                {
                    "name": "Prognose (additiv)",
                    "color": "var(--mantine-color-violet-5)",
                    "strokeDasharray": "4 4",
                },
            ],
            h=220,
            with_legend=True,
            with_dots=False,
            with_x_axis=True,
            with_y_axis=True,
            grid_axis="y",
            curve_type="monotone",
            connect_nulls=False,
            x_axis_props={
                "tickFormatter": rx.Var(
                    "((v) => { if (!v) return ''; "
                    "const p = String(v).split('-'); "
                    "return p.length === 3 ? `${p[2]}.${p[1]}.${p[0]}` : v; })"
                )
            },
            y_axis_props={
                "tickFormatter": rx.Var(
                    "((v) => { const n = Number(v); "
                    "if (!isFinite(n)) return ''; "
                    "if (Math.abs(n) >= 1000) "
                    "return (n/1000).toLocaleString('de-DE', "
                    "{maximumFractionDigits: 1}) + 'T'; "
                    "return n.toLocaleString('de-DE'); })"
                )
            },
            custom_attrs={
                "valueFormatter": rx.Var(
                    "((v) => v == null ? '' : "
                    "Number(v).toLocaleString('de-DE', "
                    "{minimumFractionDigits: 2, maximumFractionDigits: 2}))"
                )
            },
        ),
        mn.text(
            "Keine Statusdaten für das Diagramm vorhanden.",
            size="sm",
            c="dimmed",
            ta="center",
            py="xl",
        ),
    )


def _status_edit_form() -> rx.Component:
    """Inline edit form bound to status draft state vars."""
    return mn.stack(
        mn.simple_grid(
            mn.date_input(
                label="Datum",
                default_value=ProjectState.status_draft_date,
                on_change=ProjectState.set_status_draft_date,
                size="sm",
                locale="de",
                value_format="DD.MM.YYYY",
                clearable=False,
                left_section=rx.icon("calendar", size=16),
            ),
            mn.number_input(
                label="Fortschritt (%)",
                default_value=ProjectState.status_draft_progress,
                on_change=ProjectState.set_status_draft_progress,
                min=0,
                max=100,
                step=5,
                decimal_scale=0,
                fixed_decimal_scale=True,
                suffix=" %",
            ),
            mn.number_input(
                label="Budgetverbrauch (%)",
                default_value=ProjectState.status_draft_budget_usage,
                on_change=ProjectState.set_status_draft_budget_usage,
                min=0,
                max=100,
                step=5,
                decimal_scale=0,
                fixed_decimal_scale=True,
                suffix=" %",
            ),
            cols=3,
            spacing="sm",
            w="100%",
        ),
        mn.textarea(
            label="Anmerkung",
            default_value=ProjectState.status_draft_notes,
            on_change=ProjectState.set_status_draft_notes,
            size="xs",
            min_rows=2,
            auto_size=True,
            w="100%",
        ),
        mn.group(
            mn.button(
                "Speichern",
                left_section=rx.icon("save", size=14),
                size="xs",
                variant="filled",
                gap="4px",
                on_click=ProjectState.save_status_draft,
            ),
            mn.button(
                "Abbrechen",
                size="xs",
                variant="subtle",
                color="gray",
                on_click=ProjectState.collapse_status_edit,
            ),
            gap="sm",
            align="center",
            justify="end",
            pt="xs",
        ),
        gap="xs",
        w="100%",
        style={
            "borderTop": "1px solid var(--alloq-border)",
            "marginTop": "8px",
            "paddingTop": "12px",
        },
    )


def _history_row(status: rx.Var) -> rx.Component:
    """Render one row of the status history table with inline edit support."""
    is_expanded = ProjectState.expanded_status_id == status.id
    return mn.box(
        mn.group(
            mn.text(
                format_date_de(status.status_date),
                size="sm",
                fw="600",
                w="6rem",
                style={"flexShrinkg": "1"},
            ),
            mn.text(
                status.notes,
                size="xs",
                c="dimmed",
                truncate=True,
                style={"flex": "1"},
            ),
            mn.badge(
                status.progress.to_string() + " %",
                variant="light",
                color="blue",
                radius="sm",
                w="5rem",
                style={"flexShrink": "0", "textAlign": "center"},
            ),
            mn.badge(
                status.budget_spent.to_string() + " %",
                variant="light",
                color="orange",
                radius="sm",
                w="5rem",
                style={"flexShrink": "0", "textAlign": "center"},
            ),
            rx.box(
                mn.action_icon(
                    rx.cond(
                        is_expanded,
                        rx.icon("chevron_up", size=14),
                        rx.icon("chevron_down", size=14),
                    ),
                    variant="subtle",
                    size="sm",
                    on_click=ProjectState.expand_status(status.id),
                ),
                on_click=rx.stop_propagation,
            ),
            rx.box(
                mn.action_icon(
                    rx.icon("trash_2", size=14),
                    variant="subtle",
                    color="red",
                    size="sm",
                    on_click=ProjectState.delete_project_status(status.id),
                ),
                on_click=rx.stop_propagation,
            ),
            w="100%",
            align="center",
            gap="sm",
        ),
        rx.cond(
            is_expanded,
            rx.box(_status_edit_form(), on_click=rx.stop_propagation),
            rx.fragment(),
        ),
        style={
            "padding": "6px 12px",
            "borderRadius": "6px",
            "backgroundColor": "var(--alloq-item-bg, var(--alloq-surface-muted))",
            "cursor": "pointer",
        },
        on_click=ProjectState.expand_status(status.id),
    )


def _status_history() -> rx.Component:
    """Status history list, newest first."""
    return section(
        mn.stack(
            mn.group(
                mn.text("Verlauf", size="sm", fw="700", c="dimmed"),
                mn.badge(
                    ProjectState.statuses.length().to_string(),
                    variant="light",
                    radius="sm",
                    size="sm",
                ),
                gap="xs",
                align="center",
            ),
            rx.cond(
                ProjectState.statuses.length() > 0,
                mn.stack(
                    rx.foreach(ProjectState.statuses, _history_row),
                    gap="4px",
                    w="100%",
                ),
                mn.text(
                    "Noch kein Status erfasst.",
                    size="sm",
                    c="dimmed",
                    ta="center",
                    py="sm",
                ),
            ),
            gap="sm",
            w="100%",
        ),
    )


def _status_form() -> rx.Component:
    """Form to record current project status."""
    return section(
        mn.stack(
            mn.text("Status erfassen", size="sm", fw="700", c="dimmed"),
            mn.simple_grid(
                mn.date_input(
                    label="Datum",
                    default_value=ProjectState.status_date,
                    on_change=ProjectState.set_status_date,
                    size="sm",
                    locale="de",
                    value_format="DD.MM.YYYY",
                    clearable=False,
                    left_section=rx.icon("calendar", size=16),
                ),
                mn.number_input(
                    label="Fortschritt (%)",
                    default_value=ProjectState.status_progress,
                    on_change=ProjectState.set_status_progress,
                    min=0,
                    max=100,
                    step=5,
                    decimal_scale=0,
                    fixed_decimal_scale=True,
                    suffix=" %",
                ),
                mn.number_input(
                    label="Budgetverbrauch (%)",
                    default_value=ProjectState.status_budget_usage,
                    on_change=ProjectState.set_status_budget_usage,
                    min=0,
                    max=100,
                    step=5,
                    decimal_scale=0,
                    fixed_decimal_scale=True,
                    suffix=" %",
                ),
                cols=3,
                spacing="md",
                w="100%",
            ),
            mn.textarea(
                label="Anmerkung",
                placeholder="Optionale Anmerkung zum aktuellen Status…",
                value=ProjectState.status_notes,
                on_change=ProjectState.set_status_notes,
                auto_size=True,
                min_rows=2,
            ),
            mn.button(
                "Status erfassen",
                on_click=ProjectState.add_project_status,
                size="sm",
                variant="light",
            ),
            gap="sm",
            w="100%",
            key=ProjectState.status_form_version.to_string(),
        ),
    )


def status_tab() -> rx.Component:
    """Status tab: EV chart, status form and history."""
    return mn.stack(
        section(
            mn.stack(
                mn.text("Earned Value", size="sm", fw="700", c="dimmed"),
                _ev_chart(),
                _ev_summary(),
                gap="sm",
                w="100%",
            ),
        ),
        _status_form(),
        _status_history(),
        mn.space(h="2rem"),
        gap="md",
        w="100%",
        class_name="alloq-modal-scroll",
    )
