"""Multi-step Projekt planen modal."""

from __future__ import annotations

import reflex as rx
from alloq_commons.components.formatters import format_date_de
from alloq_commons.models.project import Project
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_project.states.project_plan_state import ProjectPlanState

import appkit_mantine as mn

CHART_HEIGHT = "180px"


def _status_badge(state_var: rx.Var[str]) -> rx.Component:
    return mn.badge(
        rx.match(
            state_var,
            ("Aktiv", "Aktiv"),
            ("Risiko", "Risiko"),
            ("Geplant", "Geplant"),
            ("Abgeschlossen", "Abgeschlossen"),
            state_var,
        ),
        size="sm",
        radius="xl",
        variant="light",
        color=rx.match(
            state_var,
            ("Aktiv", "green"),
            ("Risiko", "red"),
            ("Abgeschlossen", "gray"),
            "gray",
        ),
        left_section=mn.box(
            style={
                "width": "6px",
                "height": "6px",
                "borderRadius": "50%",
                "backgroundColor": rx.match(
                    state_var,
                    ("Aktiv", "var(--mantine-color-green-6)"),
                    ("Risiko", "var(--mantine-color-red-6)"),
                    ("Abgeschlossen", "var(--mantine-color-gray-6)"),
                    "var(--mantine-color-gray-6)",
                ),
            },
        ),
    )


def _project_card(project: Project) -> rx.Component:
    return mn.box(
        mn.group(
            mn.stack(
                mn.text(
                    project.name_de,
                    size="sm",
                    fw="700",
                    c="var(--alloq-text)",
                ),
                mn.text(
                    format_date_de(project.start_date)
                    + " → "
                    + format_date_de(project.end_date)
                    + " · "
                    + project.team_initials.length().to_string()
                    + " Personen",
                    size="xs",
                    c="var(--alloq-text-muted)",
                ),
                gap="2px",
                style={"flex": "1", "minWidth": "0"},
            ),
            _status_badge(project.state),
            rx.icon("chevron-right", size=18, color="var(--alloq-text-muted)"),
            gap="md",
            align="center",
            wrap="nowrap",
            w="100%",
        ),
        on_click=ProjectPlanState.select_project(project.id),
        style={
            "padding": "12px 16px",
            "borderRadius": "10px",
            "cursor": "pointer",
            "_hover": {"backgroundColor": "var(--alloq-surface-hover)"},
            "borderBottom": "1px solid var(--alloq-border)",
        },
    )


def _step_project_select() -> rx.Component:
    return mn.stack(
        mn.text_input(
            placeholder="Projekte suchen...",
            value=ProjectPlanState.search,
            on_change=ProjectPlanState.set_search,
            size="md",
            radius="md",
            mb="md",
        ),
        mn.box(
            rx.foreach(PlanningStore.available_projects, _project_card),
            style={
                "maxHeight": "60vh",
                "overflowY": "auto",
                "borderRadius": "10px",
                "border": "1px solid var(--alloq-border)",
            },
        ),
        gap="0",
        w="100%",
    )


def _info_card(label: str, value: rx.Var[str] | str) -> rx.Component:
    return mn.box(
        mn.text(
            label,
            size="xs",
            fw="700",
            c="var(--alloq-text-muted)",
            style={"letterSpacing": "0.06em", "textTransform": "uppercase"},
        ),
        mn.text(value, size="lg", fw="600", c="var(--alloq-text)"),
        style={
            "padding": "12px 16px",
            "borderRadius": "10px",
            "backgroundColor": "var(--alloq-surface-muted)",
            "flex": "1",
        },
    )


def _editable_card(
    label: str,
    value: rx.Var,
    on_change: rx.event.EventHandler,
    min_: int = 0,
    step: int = 1,
) -> rx.Component:
    return mn.box(
        mn.text(
            label,
            size="xs",
            fw="700",
            c="var(--alloq-text-muted)",
            style={"letterSpacing": "0.06em", "textTransform": "uppercase"},
        ),
        mn.number_input(
            value=value,
            on_change=on_change,
            min=min_,
            step=step,
            hide_controls=False,
            size="md",
        ),
        style={
            "padding": "12px 16px",
            "borderRadius": "10px",
            "backgroundColor": "var(--alloq-surface-muted)",
            "flex": "1",
        },
    )


def _bar(value: rx.Var[float]) -> rx.Component:
    return mn.box(
        style={
            "flex": "1",
            "minWidth": "10px",
            "height": value / ProjectPlanState.chart_max * 140,
            "backgroundColor": "var(--mantine-color-yellow-5)",
            "borderRadius": "4px 4px 0 0",
        },
    )


def _month_label(seg: dict) -> rx.Component:
    return mn.box(
        mn.text(seg["label"], size="xs", c="var(--alloq-text-muted)", fw="500"),
        style={
            "flex": seg["span"],
            "textAlign": "center",
            "padding": "4px 0",
            "borderTop": "1px solid var(--alloq-border)",
        },
    )


def _chart_stats() -> rx.Component:
    return mn.group(
        mn.text(
            "Σ "
            + ProjectPlanState.distribution_sum.to_string()
            + " PT · max "
            + ProjectPlanState.distribution_max.to_string()
            + " PT/Wo · "
            + ProjectPlanState.distribution_gtk.to_string()
            + " GTK",
            size="xs",
            c="var(--alloq-text-muted)",
        ),
        mn.text(
            "cap " + ProjectPlanState.cap_value.to_string() + " PT",
            size="xs",
            fw="600",
            c="var(--mantine-color-red-7)",
        ),
        gap="md",
        align="center",
    )


def _cap_line() -> rx.Component:
    return mn.box(
        style={
            "position": "absolute",
            "left": "12px",
            "right": "12px",
            "bottom": rx.Var.create("calc(4px + ")
            + (ProjectPlanState.cap_height_pct / 100 * 140).to_string()
            + "px)",
            "borderTop": "2px dashed var(--mantine-color-red-6)",
            "pointerEvents": "none",
            "zIndex": "2",
        },
    )


def _distribution_chart() -> rx.Component:
    return mn.stack(
        mn.group(
            mn.text(
                "Wochenverteilung (PT)", size="sm", fw="600", c="var(--alloq-text)"
            ),
            _chart_stats(),
            justify="space-between",
            w="100%",
            align="center",
        ),
        mn.box(
            mn.group(
                rx.foreach(ProjectPlanState.distribution, _bar),
                gap="3px",
                align="flex-end",
                w="100%",
                style={"height": "150px", "position": "relative"},
            ),
            _cap_line(),
            style={
                "padding": "12px 12px 4px",
                "backgroundColor": "var(--alloq-surface-muted)",
                "borderRadius": "10px",
                "position": "relative",
            },
        ),
        rx.cond(
            ProjectPlanState.month_segments.length() > 1,
            mn.group(
                rx.foreach(ProjectPlanState.month_segments, _month_label),
                gap="0",
                w="100%",
            ),
            rx.fragment(),
        ),
        gap="xs",
        w="100%",
    )


def _ramp_card(
    label: str,
    value: rx.Var,
    on_change: rx.event.EventHandler,
    max_var: rx.Var,
    left_label: str,
    right_label: str,
) -> rx.Component:
    return mn.box(
        mn.stack(
            mn.group(
                mn.text(label, size="sm", fw="500", c="var(--alloq-text)"),
                mn.text(
                    value.to_string() + " Wo.",
                    size="md",
                    fw="700",
                    c="var(--alloq-text)",
                ),
                justify="space-between",
                w="100%",
                align="center",
            ),
            mn.slider(
                value=value,
                on_change=on_change,
                min=0,
                max=max_var,
                step=1,
                color="dark",
                size="md",
                radius="xl",
            ),
            mn.group(
                mn.text(left_label, size="xs", c="var(--alloq-text-muted)"),
                mn.text(right_label, size="xs", c="var(--alloq-text-muted)"),
                justify="space-between",
                w="100%",
            ),
            gap="sm",
        ),
        style={
            "padding": "16px 18px",
            "borderRadius": "14px",
            "backgroundColor": "var(--alloq-surface-muted)",
            "border": "1px solid var(--alloq-border)",
            "flex": "1",
        },
    )


def _capacity_card() -> rx.Component:
    return mn.box(
        mn.stack(
            mn.group(
                mn.text("Kapazität / Wo.", size="sm", fw="500", c="var(--alloq-text)"),
                mn.text(
                    ProjectPlanState.gtk_count.to_string() + " GTK",
                    size="md",
                    fw="700",
                    c="var(--alloq-text)",
                ),
                justify="space-between",
                w="100%",
                align="center",
            ),
            mn.slider(
                value=ProjectPlanState.gtk_count,
                on_change=ProjectPlanState.set_gtk_count,
                min=0.5,
                max=30,
                step=0.5,
                color="dark",
                size="md",
                radius="xl",
            ),
            mn.text(
                ProjectPlanState.cap_label,
                size="xs",
                c="var(--alloq-text-muted)",
                ta="right",
            ),
            gap="sm",
        ),
        style={
            "padding": "16px 18px",
            "borderRadius": "14px",
            "backgroundColor": "light-dark("
            "var(--mantine-color-yellow-0), rgba(241,202,69,0.08))",
            "border": "1px solid var(--mantine-color-yellow-3)",
            "flex": "1",
        },
    )


def _step_verteilung() -> rx.Component:
    return mn.stack(
        mn.group(
            _info_card("Start → Ende", ProjectPlanState.date_range_label),
            _editable_card(
                "Wochen",
                ProjectPlanState.num_weeks,
                ProjectPlanState.set_num_weeks,
                min_=1,
                step=1,
            ),
            _editable_card(
                "PT-Bedarf gesamt",
                ProjectPlanState.total_pt,
                ProjectPlanState.set_total_pt,
                min_=0,
                step=10,
            ),
            gap="md",
            w="100%",
            align="stretch",
        ),
        mn.group(
            _ramp_card(
                "Ramp-up",
                ProjectPlanState.ramp_up,
                ProjectPlanState.set_ramp_up,
                ProjectPlanState.num_weeks,
                "sofort",
                "langsam",
            ),
            _ramp_card(
                "Ramp-down",
                ProjectPlanState.ramp_down,
                ProjectPlanState.set_ramp_down,
                ProjectPlanState.num_weeks,
                "abrupt",
                "langsam",
            ),
            _capacity_card(),
            gap="md",
            w="100%",
            align="stretch",
            grow=True,
        ),
        rx.cond(
            ProjectPlanState.shortfall,
            mn.alert(
                ProjectPlanState.shortfall_msg,
                icon=rx.icon("triangle-alert", size=16),
                color="red",
                variant="light",
                radius="md",
            ),
            rx.fragment(),
        ),
        _distribution_chart(),
        gap="lg",
        w="100%",
    )


def _step_placeholder(title: str) -> rx.Component:
    return mn.center(
        mn.stack(
            mn.text(title, size="lg", fw="600", c="var(--alloq-text-muted)"),
            mn.text(
                "Noch nicht implementiert.",
                size="sm",
                c="var(--alloq-text-muted)",
            ),
            align="center",
            gap="xs",
        ),
        py="xl",
    )


def _preview_bar(bar: dict) -> rx.Component:
    return mn.tooltip(
        mn.box(
            style={
                "flex": "1",
                "minWidth": "6px",
                "height": bar["h_pct"] + "%",
                "backgroundColor": "var(--mantine-color-yellow-5)",
                "borderRadius": "2px 2px 0 0",
                "minHeight": "2px",
            },
        ),
        label=bar["pt"] + " PT",
        position="top",
        with_arrow=True,
    )


def _preview_row(row: dict) -> rx.Component:
    return mn.box(
        mn.group(
            mn.avatar(
                name=row["name"],
                color="var(--alloq-accent-strong)",
                size="md",
                radius="xl",
            ),
            mn.stack(
                mn.text(row["name"], size="sm", fw="600", c="var(--alloq-text)"),
                mn.text(row["role"], size="xs", c="var(--alloq-text-muted)"),
                gap="2px",
                style={"flex": "1", "minWidth": "0"},
            ),
            mn.box(
                mn.group(
                    rx.foreach(row["bars"], _preview_bar),
                    gap="2px",
                    align="flex-end",
                    style={"height": "44px", "width": "100%"},
                ),
                style={
                    "flex": "2",
                    "minWidth": "180px",
                    "padding": "4px 8px",
                    "backgroundColor": "var(--alloq-surface-muted)",
                    "borderRadius": "8px",
                },
            ),
            mn.stack(
                mn.text(
                    row["planned_label"],
                    size="sm",
                    fw="700",
                    c="var(--alloq-text)",
                    ta="right",
                ),
                mn.text(
                    "max " + row["weekly_max"] + " PT/Wo",
                    size="xs",
                    c="var(--alloq-text-muted)",
                    ta="right",
                ),
                gap="2px",
                style={"flexShrink": "0", "minWidth": "100px"},
            ),
            gap="md",
            align="center",
            wrap="nowrap",
            w="100%",
        ),
        style={
            "padding": "10px 14px",
            "borderBottom": "1px solid var(--alloq-border)",
        },
    )


def _step_preview() -> rx.Component:
    return mn.stack(
        mn.group(
            _stat_card(
                "Projekt",
                ProjectPlanState.selected_project_code
                + " · "
                + ProjectPlanState.selected_project_name,
            ),
            _stat_card(
                "Zeitraum",
                ProjectPlanState.effective_weeks.to_string() + " Wochen",
            ),
            _stat_card(
                "Mitarbeiter",
                ProjectPlanState.preview_emp_count.to_string(),
            ),
            _stat_card(
                "Plan gesamt",
                ProjectPlanState.preview_total_pt.to_string() + " PT",
            ),
            gap="sm",
            w="100%",
            wrap="wrap",
            align="stretch",
        ),
        rx.cond(
            ProjectPlanState.preview_rows.length() > 0,
            mn.box(
                rx.foreach(ProjectPlanState.preview_rows, _preview_row),
                style={
                    "borderRadius": "10px",
                    "border": "1px solid var(--alloq-border)",
                    "overflow": "hidden",
                },
            ),
            mn.alert(
                "Keine Allokationen geplant. Schritt zurück und PT setzen.",
                icon=rx.icon("triangle-alert", size=16),
                color="orange",
                variant="light",
                radius="md",
            ),
        ),
        gap="md",
        w="100%",
    )


def _role_chip(opt: dict) -> rx.Component:
    active = ProjectPlanState.employee_role_filter == opt["value"]
    return mn.button(
        opt["label"],
        variant=rx.cond(active, "filled", "default"),
        color="dark",
        size="xs",
        radius="xl",
        on_click=ProjectPlanState.set_employee_role_filter(opt["value"]),
    )


def _stat_card(
    label: str,
    value: rx.Var[str] | str,
    accent: rx.Var[str] | str = "var(--alloq-text)",
) -> rx.Component:
    return mn.box(
        mn.text(
            label,
            size="xs",
            fw="700",
            c="var(--alloq-text-muted)",
            style={"letterSpacing": "0.06em", "textTransform": "uppercase"},
        ),
        mn.text(value, size="lg", fw="700", c=accent),
        style={
            "padding": "10px 14px",
            "borderRadius": "10px",
            "backgroundColor": "var(--alloq-surface-muted)",
            "border": "1px solid var(--alloq-border)",
            "flex": "1",
            "minWidth": "0",
        },
    )


def _capacity_summary() -> rx.Component:
    return mn.group(
        _stat_card(
            "Bedarf gesamt",
            ProjectPlanState.required_pt_total.to_string() + " PT",
        ),
        _stat_card(
            "Ausgewählt",
            ProjectPlanState.selected_capacity_pt.to_string() + " PT",
            accent=rx.cond(
                ProjectPlanState.selected_capacity_pt
                >= ProjectPlanState.required_pt_total,
                "var(--mantine-color-green-7)",
                "var(--alloq-text)",
            ),
        ),
        _stat_card(
            "Verfügbar im Zeitraum",
            ProjectPlanState.available_capacity_pt.to_string() + " PT",
        ),
        gap="sm",
        w="100%",
        align="stretch",
        wrap="nowrap",
    )


def _role_requirement_card(rc: dict) -> rx.Component:
    return mn.box(
        mn.group(
            mn.stack(
                mn.text(
                    rc["role_name"],
                    size="xs",
                    fw="700",
                    c="var(--alloq-text-muted)",
                    style={
                        "letterSpacing": "0.06em",
                        "textTransform": "uppercase",
                    },
                ),
                mn.group(
                    mn.text(
                        rc["assigned_pt"],
                        size="md",
                        fw="700",
                        c=rx.cond(
                            rc["covered"] == "true",
                            "var(--mantine-color-green-7)",
                            "var(--alloq-text)",
                        ),
                    ),
                    mn.text(
                        "/ " + rc["required_pt"] + " PT",
                        size="sm",
                        c="var(--alloq-text-muted)",
                    ),
                    gap="4px",
                    align="baseline",
                ),
                gap="2px",
                style={"flex": "1", "minWidth": "0"},
            ),
            rx.cond(
                rc["covered"] == "true",
                rx.icon(
                    "circle-check-big",
                    size=18,
                    color="var(--mantine-color-green-6)",
                ),
                rx.icon(
                    "circle-alert",
                    size=18,
                    color="var(--mantine-color-orange-6)",
                ),
            ),
            gap="sm",
            align="center",
            wrap="nowrap",
            w="100%",
        ),
        style={
            "padding": "10px 14px",
            "borderRadius": "10px",
            "backgroundColor": "var(--alloq-surface-muted)",
            "border": "1px solid var(--alloq-border)",
            "flex": "1",
            "minWidth": "180px",
        },
    )


def _role_requirements_row() -> rx.Component:
    return rx.cond(
        ProjectPlanState.required_roles_display.length() > 0,
        mn.stack(
            mn.text(
                "Rollenbedarf",
                size="xs",
                fw="700",
                c="var(--alloq-text-muted)",
                style={"letterSpacing": "0.06em", "textTransform": "uppercase"},
            ),
            mn.group(
                rx.foreach(
                    ProjectPlanState.required_roles_display,
                    _role_requirement_card,
                ),
                gap="sm",
                w="100%",
                wrap="wrap",
                align="stretch",
            ),
            gap="xs",
            w="100%",
        ),
        rx.fragment(),
    )


def _emp_plan_inputs(emp: dict) -> rx.Component:
    return mn.group(
        mn.select(
            data=emp["role_options"],
            value=emp["role_value"],
            on_change=ProjectPlanState.set_emp_role(emp["id"]),
            placeholder="Rolle",
            allow_deselect=False,
            size="xs",
            style={"width": "150px"},
        ),
        mn.number_input(
            value=emp["planned_pct"],
            on_change=ProjectPlanState.set_emp_planned_pct(emp["id"]),
            min=0,
            max=100,
            step=5,
            hide_controls=False,
            size="xs",
            style={"width": "92px"},
            suffix=" %",
        ),
        mn.number_input(
            value=emp["planned_pt"],
            on_change=ProjectPlanState.set_emp_planned_pt(emp["id"]),
            min=0,
            max=emp["available_pt"],
            step=1,
            hide_controls=False,
            size="xs",
            style={"width": "108px"},
            suffix=" PT",
        ),
        gap="xs",
        align="center",
        wrap="nowrap",
        style={"flexShrink": "0"},
    )


def _employee_row(emp: dict) -> rx.Component:
    return mn.box(
        mn.group(
            mn.box(
                mn.group(
                    mn.checkbox(
                        checked=emp["selected"],
                        color="dark",
                        size="md",
                        style={"pointerEvents": "none"},
                    ),
                    mn.avatar(
                        name=emp["name"],
                        color="var(--alloq-accent-strong)",
                        size="md",
                        radius="xl",
                    ),
                    mn.stack(
                        mn.text(
                            emp["name"], size="sm", fw="600", c="var(--alloq-text)"
                        ),
                        mn.text(emp["roles"], size="xs", c="var(--alloq-text-muted)"),
                        gap="2px",
                        style={"flex": "1", "minWidth": "0"},
                    ),
                    gap="md",
                    align="center",
                    wrap="nowrap",
                    style={"flex": "1", "minWidth": "0"},
                ),
                on_click=ProjectPlanState.toggle_employee(emp["id"]),
                style={
                    "flex": "1",
                    "minWidth": "0",
                    "cursor": "pointer",
                    "padding": "10px 0",
                },
            ),
            rx.cond(
                emp["selected"],
                _emp_plan_inputs(emp),
                mn.stack(
                    mn.text(
                        emp["available_label"],
                        size="sm",
                        fw="700",
                        c="var(--alloq-text)",
                        ta="right",
                    ),
                    mn.text(
                        emp["sub_label"],
                        size="xs",
                        c="var(--alloq-text-muted)",
                        ta="right",
                    ),
                    gap="2px",
                    style={"flexShrink": "0"},
                ),
            ),
            mn.badge(
                emp["seniority"],
                size="sm",
                radius="xl",
                variant="light",
                color="gray",
            ),
            gap="md",
            align="center",
            wrap="nowrap",
            w="100%",
        ),
        style={
            "padding": "0 14px",
            "borderBottom": "1px solid var(--alloq-border)",
            "_hover": {"backgroundColor": "var(--alloq-surface-hover)"},
            "backgroundColor": rx.cond(
                emp["selected"],
                "var(--alloq-surface-muted)",
                "transparent",
            ),
        },
    )


def _step_mitarbeiter() -> rx.Component:
    return mn.stack(
        _capacity_summary(),
        _role_requirements_row(),
        mn.box(
            style={
                "height": "1px",
                "backgroundColor": "var(--alloq-border)",
                "width": "100%",
            },
        ),
        mn.group(
            mn.text(
                ProjectPlanState.selected_count.to_string()
                + " von "
                + ProjectPlanState.filtered_count.to_string()
                + " ausgewählt",
                size="sm",
                fw="600",
                c="var(--alloq-text)",
            ),
            mn.group(
                mn.button(
                    "Alle auswählen",
                    variant="subtle",
                    color="dark",
                    size="xs",
                    radius="xl",
                    on_click=ProjectPlanState.select_all_filtered,
                ),
                mn.button(
                    "Auswahl löschen",
                    variant="subtle",
                    color="dark",
                    size="xs",
                    radius="xl",
                    on_click=ProjectPlanState.clear_employee_selection,
                ),
                gap="2px",
            ),
            justify="space-between",
            w="100%",
            align="center",
        ),
        mn.group(
            rx.foreach(ProjectPlanState.role_options_data, _role_chip),
            gap="xs",
            wrap="wrap",
        ),
        mn.box(
            rx.foreach(ProjectPlanState.filtered_employees, _employee_row),
            style={
                "borderRadius": "10px",
                "border": "1px solid var(--alloq-border)",
                "overflow": "hidden",
            },
        ),
        gap="md",
        w="100%",
    )


def _stepper() -> rx.Component:
    return mn.stepper(
        mn.stepper.step(label="Projekt", description=""),
        mn.stepper.step(label="Verteilung", description=""),
        mn.stepper.step(label="Mitarbeiter", description=""),
        mn.stepper.step(label="Vorschau", description=""),
        active=ProjectPlanState.step,
        size="sm",
        color="dark",
        w="100%",
    )


def _content() -> rx.Component:
    return rx.match(
        ProjectPlanState.step,
        (0, _step_project_select()),
        (1, _step_verteilung()),
        (2, _step_mitarbeiter()),
        (3, _step_preview()),
        rx.fragment(),
    )


def _footer() -> rx.Component:
    return mn.group(
        mn.button(
            "Abbrechen",
            variant="default",
            radius="xl",
            on_click=ProjectPlanState.close_modal,
        ),
        mn.group(
            rx.cond(
                ProjectPlanState.step > 0,
                mn.button(
                    "Zurück",
                    variant="default",
                    radius="xl",
                    on_click=ProjectPlanState.prev_step,
                ),
                rx.fragment(),
            ),
            rx.cond(
                ProjectPlanState.step < 3,  # noqa: PLR2004
                mn.button(
                    "Weiter →",
                    variant="filled",
                    color="dark",
                    radius="xl",
                    on_click=ProjectPlanState.next_step,
                ),
                mn.button(
                    "Speichern",
                    variant="filled",
                    color="dark",
                    radius="xl",
                    on_click=ProjectPlanState.save_plan,
                ),
            ),
            gap="sm",
        ),
        justify="space-between",
        w="100%",
        pt="md",
    )


def project_plan_modal() -> rx.Component:
    return mn.modal(
        mn.box(
            mn.box(
                mn.stack(
                    _stepper(),
                    _content(),
                    gap="lg",
                ),
                style={
                    "overflowY": "auto",
                    "overflowX": "hidden",
                    "flex": "1",
                    "minHeight": "0",
                    "paddingRight": "8px",
                },
            ),
            mn.box(
                _footer(),
                style={
                    "borderTop": "1px solid var(--alloq-border)",
                    "backgroundColor": "var(--alloq-surface-solid)",
                    "paddingTop": "12px",
                    "marginTop": "12px",
                    "flexShrink": "0",
                },
            ),
            style={
                "display": "flex",
                "flexDirection": "column",
                "height": "min(85vh, 900px)",
                "width": "100%",
            },
        ),
        title=ProjectPlanState.title,
        opened=ProjectPlanState.is_open,
        on_close=ProjectPlanState.close_modal,
        size="xl",
        centered=True,
        radius="lg",
        padding="lg",
    )


_ = CHART_HEIGHT
