import reflex as rx
from alloq_project.states.planning_grid_state import PlanningStore

import appkit_mantine as mn


class _PlanningFilterRow(rx.Component):
    """Measure inline controls and reveal overflowing filters on hover."""

    library = rx.asset("planning_filter_row.jsx", shared=True).importable_path
    tag = "PlanningFilterRow"


def _ms_class(has_mehr: rx.Var) -> rx.Var:
    """CSS class for filter multi-select, adds 'has-mehr' when needed."""
    return rx.cond(has_mehr, "alloq-filter-ms has-mehr", "alloq-filter-ms")


def planning_filter_row() -> rx.Component:
    """Row of inline filters and view toggles for the planning page."""
    return _PlanningFilterRow.create(
        # View modes with custom React node as label (icons + text)
        mn.segmented_control(
            data=[
                {
                    "value": "Grid",
                    "label": mn.center(
                        rx.icon("layout-grid", size=16),
                        rx.text("Team", size="2"),
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
                {
                    "value": "Heatmap",
                    "label": mn.center(
                        rx.icon("grid-3x3", size=16),
                        rx.text("Heatmap", size="2"),
                        gap="4px",
                    ),
                },
                {
                    "value": "Abwesenheiten",
                    "label": mn.center(
                        rx.icon("chart-gantt", size=16),
                        rx.text("Abwesenheiten", size="2"),
                        gap="4px",
                    ),
                },
            ],
            value=PlanningStore.view_mode,
            on_change=PlanningStore.set_view_mode,
            color="dark",
            radius="md",
            bg="var(--alloq-surface-solid)",
        ),
        # Time range
        mn.segmented_control(
            data=["3 Monate", "6 Monate", "12 Monate"],
            value=PlanningStore.time_range,
            on_change=PlanningStore.set_time_range,
            color="alloqTeal.5",
            radius="md",
            bg="var(--alloq-surface-solid)",
        ),
        # Employee filter
        mn.multi_select(
            data=PlanningStore.employee_select_options,
            value=PlanningStore.employee_filter.to(list[str]),
            on_change=PlanningStore.set_employee_filter,
            placeholder="Mitarbeiter",
            searchable=True,
            clearable=True,
            combobox_props={"withinPortal": False},
            w="12rem",
            class_name=_ms_class(PlanningStore.employee_filter.length() > 0),
            style={"--alloq-mehr": PlanningStore.employee_filter_label},
        ),
        # Project filter
        mn.multi_select(
            data=PlanningStore.project_select_options,
            value=PlanningStore.project_filter.to(list[str]),
            on_change=PlanningStore.set_project_filter,
            placeholder="Projekte",
            searchable=True,
            clearable=True,
            combobox_props={"withinPortal": False},
            w="12rem",
            class_name=_ms_class(PlanningStore.project_filter.length() > 0),
            style={"--alloq-mehr": PlanningStore.project_filter_label},
        ),
        # Role filter
        mn.multi_select(
            data=PlanningStore.role_select_options,
            value=PlanningStore.role_filter.to(list[str]),
            on_change=PlanningStore.set_role_filter,
            placeholder="Rollen",
            searchable=True,
            clearable=True,
            combobox_props={"withinPortal": False},
            w="12rem",
            class_name=_ms_class(PlanningStore.role_filter.length() > 0),
            style={"--alloq-mehr": PlanningStore.role_filter_label},
        ),
        mn.switch(
            label="Nur verfügbare",
            checked=PlanningStore.available_only,
            on_change=PlanningStore.set_available_only,
            color="alloqTeal.5",
            size="sm",
        ),
    )
