import reflex as rx
from alloq_project.states.planning_state import PlanningState

import appkit_mantine as mn


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
                    "value": "Kapazität",
                    "label": mn.center(
                        rx.icon("chart-bar", size=16),
                        rx.text("Kapazität", size="2"),
                        gap="4px",
                    ),
                },
            ],
            value=PlanningState.view_mode,
            on_change=PlanningState.set_view_mode,
            color="dark",
            radius="md",
            bg="white",
        ),
        # Time range
        mn.segmented_control(
            data=["3 Monate", "6 Monate", "12 Monate"],
            value=PlanningState.time_range,
            on_change=PlanningState.set_time_range,
            color="alloqWarm.5",
            radius="md",
            bg="white",
            style={
                "& .mantine-SegmentedControl-label[data-active]": {
                    "color": "black !important"
                }
            },
        ),
        # Project filter
        mn.select(
            data=PlanningState.project_select_options,
            value=PlanningState.project_filter,
            on_change=PlanningState.set_project_filter,
            placeholder="Projekte",
            searchable=True,
            w="12rem",
        ),
        # Role filter
        mn.select(
            data=PlanningState.role_select_options,
            value=PlanningState.role_filter,
            on_change=PlanningState.set_role_filter,
            placeholder="Rollen",
            searchable=True,
            w="12rem",
        ),
        # Employee filter
        mn.select(
            data=PlanningState.employee_select_options,
            value=PlanningState.employee_filter,
            on_change=PlanningState.set_employee_filter,
            placeholder="Mitarbeiter",
            searchable=True,
            w="12rem",
        ),
        gap="md",
        align="center",
        w="100%",
        pb="md",
    )
