import reflex as rx
from alloq_project.states.planning_grid_state import PlanningGridState
from alloq_project.states.planning_project_view_state import (
    PlanningProjectViewState,
)
from alloq_project.states.planning_state import PlanningState

import appkit_mantine as mn


def _ms_class(has_mehr: rx.Var) -> rx.Var:
    """CSS class for filter multi-select, adds 'has-mehr' when needed."""
    return rx.cond(has_mehr, "alloq-filter-ms has-mehr", "alloq-filter-ms")


def planning_filter_row() -> rx.Component:
    """Row of inline filters and view toggles for the planning page."""
    return mn.group(
        # View modes with custom React node as label (icons + text)
        mn.segmented_control(
            data=[
                {
                    "value": "Grid",
                    "label": mn.center(
                        rx.icon("layout-grid", size=16),
                        rx.text("Grid", size="2"),
                        gap="4px",
                    ),
                },
                {
                    "value": "Heatmap",
                    "label": mn.center(
                        rx.icon("grid-3x3", size=16),
                        rx.text("Heatmap", size="2"),
                        gap="4px",
                    ),
                },
                {
                    "value": "Projekte",
                    "label": mn.center(
                        rx.icon("chart-bar", size=16),
                        rx.text("Projekte", size="2"),
                        gap="4px",
                    ),
                },
            ],
            value=PlanningState.view_mode,
            on_change=PlanningState.set_view_mode,
            color="dark",
            radius="md",
            bg="var(--alloq-surface-solid)",
        ),
        # Time range
        mn.segmented_control(
            data=["3 Monate", "6 Monate", "12 Monate"],
            value=PlanningState.time_range,
            on_change=PlanningState.set_time_range,
            color="alloqWarm.5",
            radius="md",
            bg="var(--alloq-surface-solid)",
            style={
                "& .mantine-SegmentedControl-label[data-active]": {
                    "color": "black !important"
                }
            },
        ),
        # Project filter
        mn.multi_select(
            data=PlanningState.project_select_options,
            value=PlanningGridState.project_filter,
            on_change=[
                PlanningGridState.set_project_filter,
                PlanningProjectViewState.set_project_filter,
            ],
            placeholder="Projekte",
            searchable=True,
            clearable=True,
            w="12rem",
            class_name=_ms_class(PlanningGridState.project_filter.length() > 0),
            style={"--alloq-mehr": PlanningGridState.project_filter_label},
        ),
        # Role filter
        mn.multi_select(
            data=PlanningState.role_select_options,
            value=PlanningGridState.role_filter,
            on_change=[
                PlanningGridState.set_role_filter,
                PlanningProjectViewState.set_role_filter,
            ],
            placeholder="Rollen",
            searchable=True,
            clearable=True,
            w="12rem",
            class_name=_ms_class(PlanningGridState.role_filter.length() > 0),
            style={"--alloq-mehr": PlanningGridState.role_filter_label},
        ),
        # Employee filter
        mn.multi_select(
            data=PlanningState.employee_select_options,
            value=PlanningGridState.employee_filter,
            on_change=[
                PlanningGridState.set_employee_filter,
                PlanningProjectViewState.set_employee_filter,
            ],
            placeholder="Mitarbeiter",
            searchable=True,
            clearable=True,
            w="12rem",
            class_name=_ms_class(PlanningGridState.employee_filter.length() > 0),
            style={"--alloq-mehr": PlanningGridState.employee_filter_label},
        ),
        gap="md",
        align="center",
        w="100%",
        pb="md",
    )
