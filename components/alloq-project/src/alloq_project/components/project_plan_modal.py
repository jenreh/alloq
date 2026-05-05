"""Multi-step Projekt planen modal."""

from __future__ import annotations

import reflex as rx
from alloq_commons.models.project import Project
from alloq_project.states.planning_state import PlanningState
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
            mn.box(
                mn.text(
                    project.code.to_string()[:3].upper(),
                    fw="700",
                    size="sm",
                    c="white",
                ),
                style={
                    "width": "44px",
                    "height": "44px",
                    "borderRadius": "8px",
                    "backgroundColor": project.color,
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "flexShrink": "0",
                },
            ),
            mn.stack(
                mn.text(
                    project.name_de,
                    size="sm",
                    fw="700",
                    c="var(--alloq-text)",
                ),
                mn.text(
                    project.code
                    + " · "
                    + project.start_date.to_string()
                    + " → "
                    + project.end_date.to_string()
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
            rx.foreach(PlanningState.available_projects, _project_card),
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
        (2, _step_placeholder("Mitarbeiter")),
        (3, _step_placeholder("Vorschau")),
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
                    on_click=ProjectPlanState.close_modal,
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
