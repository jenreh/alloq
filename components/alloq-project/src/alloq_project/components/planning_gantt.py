"""Resource absence Gantt chart with the planning page's weekly time axis."""

import reflex as rx
from alloq_project.components.planning_shared import (
    GRID_WRAPPER_STYLE,
    HEADER_BLOCK_STYLE,
    LABEL_CELL_BASE,
    STICKY_LEFT_BODY,
    WEEK_COL_WIDTH,
    current_week_bg,
    grid_row,
    label_th,
    month_cell,
    week_label_cell,
)
from alloq_project.services.planning_gantt import GANTT_LANE_PX, GANTT_PADDING_PX
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_project.states.planning_models import (
    AbsenceGanttBar,
    AbsenceGanttRow,
    WeekColumn,
)
from reflex.vars import ObjectVar

import appkit_mantine as mn


def _absence_bar(bar: ObjectVar[AbsenceGanttBar]) -> rx.Component:
    return mn.tooltip(
        mn.box(
            mn.text(bar.label, size="xs", fw="600", truncate=True),
            custom_attrs={"aria-label": bar.tooltip, "tabIndex": 0},
            style={
                "position": "absolute",
                "left": bar.left_px.to_string() + "px",
                "width": bar.width_px.to_string() + "px",
                "top": (bar.lane.to(int) * GANTT_LANE_PX + GANTT_PADDING_PX).to_string()
                + "px",
                "height": "24px",
                "padding": "3px 0",
                "overflow": "hidden",
                "borderRadius": "4px",
                "backgroundColor": "var(--alloq-accent-strong)",
                "color": "var(--mantine-color-white)",
                "textAlign": "center",
                "cursor": "default",
                "_focusVisible": {"outline": "2px solid var(--alloq-text)"},
            },
        ),
        label=mn.text(bar.tooltip, size="xs", style={"whiteSpace": "pre-line"}),
        with_arrow=True,
        multiline=True,
        w=300,
    )


def _week_background(week: ObjectVar[WeekColumn]) -> rx.Component:
    return mn.box(
        style={
            "width": WEEK_COL_WIDTH,
            "flexShrink": "0",
            "height": "100%",
            "borderRight": "1px solid var(--alloq-border)",
            "backgroundColor": current_week_bg(week.key),
        },
    )


def _resource_row(row: ObjectVar[AbsenceGanttRow]) -> rx.Component:
    return grid_row(
        mn.box(
            mn.group(
                mn.avatar(name=row.name, size="md", radius="xl"),
                mn.stack(
                    mn.text(row.name, size="sm", fw="700", truncate=True),
                    rx.cond(
                        row.job_title != "",
                        mn.text(
                            row.job_title,
                            size="xs",
                            c="var(--alloq-text-muted)",
                            truncate=True,
                        ),
                    ),
                    gap="2px",
                    style={"minWidth": "0"},
                ),
                gap="sm",
                wrap="nowrap",
            ),
            style={**LABEL_CELL_BASE, **STICKY_LEFT_BODY},
        ),
        mn.box(
            mn.box(
                rx.foreach(PlanningStore.weeks, _week_background),
                style={"display": "flex", "position": "absolute", "inset": "0"},
            ),
            rx.foreach(row.bars, _absence_bar),
            style={
                "gridColumn": "2 / -1",
                "position": "relative",
                "borderBottom": "1px solid var(--alloq-border)",
                "overflow": "hidden",
            },
        ),
        attrs={"data-resource-id": row.real_id.to_string()},
        style={"minHeight": row.height_px.to_string() + "px"},
    )


def planning_gantt() -> rx.Component:
    return rx.cond(
        PlanningStore.is_loaded,
        mn.box(
            mn.box(
                grid_row(
                    label_th("Mitarbeiter", accent=True),
                    rx.foreach(PlanningStore.month_spans, month_cell),
                ),
                grid_row(
                    label_th("Abwesenheiten"),
                    rx.foreach(PlanningStore.weeks, week_label_cell),
                ),
                style=HEADER_BLOCK_STYLE,
            ),
            rx.foreach(PlanningStore.absence_gantt_rows, _resource_row),
            rx.cond(
                PlanningStore.absence_gantt_rows.length() == 0,
                mn.center(
                    mn.text(
                        "Keine Abwesenheiten für den gewählten Zeitraum und Filter.",
                        size="sm",
                        c="var(--alloq-text-muted)",
                    ),
                    py="xl",
                ),
            ),
            id="planning-gantt-root",
            style=GRID_WRAPPER_STYLE,
        ),
        mn.center(
            mn.group(rx.spinner(size="3"), mn.text("Lade Abwesenheiten...", size="sm")),
            py="xl",
        ),
    )
