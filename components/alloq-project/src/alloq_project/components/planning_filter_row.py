import reflex as rx
from alloq_project.states.planning_grid_state import PlanningStore

import appkit_mantine as mn

VIEW_MODES: list[tuple[str, str, str]] = [
    ("Grid", "Team", "users"),
    ("Projekte", "Projekte", "folder-kanban"),
    ("Abwesenheiten", "Abwesenheiten", "calendar-off"),
]


class _PlanningFilterRow(rx.Component):
    """Measure inline controls and reveal overflowing filters on hover."""

    library = rx.asset("planning_filter_row.jsx", shared=True).importable_path
    tag = "PlanningFilterRow"


def _ms_class(has_mehr: rx.Var) -> rx.Var:
    """CSS class for filter multi-select, adds 'has-mehr' when needed."""
    return rx.cond(has_mehr, "alloq-filter-ms has-mehr", "alloq-filter-ms")


def planning_view_switch() -> rx.Component:
    """Segmented control for the planning views, shown in the toolbar."""
    return mn.segmented_control(
        data=[
            {
                "value": value,
                "label": mn.center(
                    rx.icon(icon, size=14, stroke_width=1.8),
                    mn.text(label, fz="12.5px"),
                    gap="5px",
                ),
            }
            for value, label, icon in VIEW_MODES
        ],
        value=PlanningStore.view_mode,
        on_change=PlanningStore.set_view_mode,
        size="xs",
        radius="md",
        class_name="aq-segmented",
    )


def planning_filter_row() -> rx.Component:
    """Scope bar of the planning page: time range, filters, availability."""
    return _PlanningFilterRow.create(
        # Time range
        mn.segmented_control(
            data=["3 Monate", "6 Monate", "12 Monate"],
            value=PlanningStore.time_range,
            on_change=PlanningStore.set_time_range,
            size="xs",
            radius="md",
            class_name="aq-segmented",
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
            size="xs",
            w="11rem",
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
            size="xs",
            w="11rem",
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
            size="xs",
            w="11rem",
            class_name=_ms_class(PlanningStore.role_filter.length() > 0),
            style={"--alloq-mehr": PlanningStore.role_filter_label},
        ),
        mn.switch(
            label="Nur verfügbare",
            checked=PlanningStore.available_only,
            on_change=PlanningStore.set_available_only,
            color="blue",
            size="xs",
        ),
        mn.switch(
            label="Interne & Abwesenheit ausblenden",
            checked=PlanningStore.hide_internal,
            on_change=PlanningStore.set_hide_internal,
            color="blue",
            size="xs",
        ),
    )


def absence_filter_row() -> rx.Component:
    """Scope bar of the absence view: time range, people, roles and summary."""
    gantt = PlanningStore.absence_gantt
    return _PlanningFilterRow.create(
        mn.segmented_control(
            data=["3 Monate", "6 Monate", "12 Monate"],
            value=PlanningStore.time_range,
            on_change=PlanningStore.set_time_range,
            size="xs",
            radius="md",
            class_name="aq-segmented",
        ),
        mn.multi_select(
            data=PlanningStore.employee_select_options,
            value=PlanningStore.employee_filter.to(list[str]),
            on_change=PlanningStore.set_employee_filter,
            placeholder="Mitarbeiter",
            searchable=True,
            clearable=True,
            combobox_props={"withinPortal": False},
            size="xs",
            w="11rem",
            class_name=_ms_class(PlanningStore.employee_filter.length() > 0),
            style={"--alloq-mehr": PlanningStore.employee_filter_label},
        ),
        mn.multi_select(
            data=PlanningStore.role_select_options,
            value=PlanningStore.role_filter.to(list[str]),
            on_change=PlanningStore.set_role_filter,
            placeholder="Rollen",
            searchable=True,
            clearable=True,
            combobox_props={"withinPortal": False},
            size="xs",
            w="11rem",
            class_name=_ms_class(PlanningStore.role_filter.length() > 0),
            style={"--alloq-mehr": PlanningStore.role_filter_label},
        ),
        mn.switch(
            label="Ganzes Team zeigen",
            checked=PlanningStore.absence_show_all,
            on_change=PlanningStore.set_absence_show_all,
            color="blue",
            size="xs",
        ),
        mn.badge(
            gantt.total_label,
            variant="light",
            color="gray",
            radius="xl",
            size="lg",
            tt="none",
            fw=500,
        ),
        rx.cond(
            gantt.bottleneck_label != "",
            mn.tooltip(
                mn.badge(
                    gantt.bottleneck_label,
                    left_section=rx.icon("triangle-alert", size=13),
                    variant="light",
                    color="red",
                    radius="xl",
                    size="lg",
                    tt="none",
                    fw=600,
                ),
                label=mn.text(
                    gantt.bottleneck_title,
                    size="xs",
                    style={"whiteSpace": "pre-line"},
                ),
                multiline=True,
                w=320,
                with_arrow=True,
            ),
            rx.fragment(),
        ),
    )
