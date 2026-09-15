from typing import Any

import reflex as rx
from alloq_commons.components.formatters import de_number, format_date_de_named
from alloq_commons.components.table_styles import (
    NO_WRAP_CELL_STYLE,
    TABLE_HEADER_STYLE,
    TABLE_STYLE,
    TABLE_WRAPPER_STYLE,
)
from alloq_commons.models.project import Project
from alloq_project.components.project_card import (
    project_initials,
    status_color,
    team_initial,
)
from alloq_project.states.project_state import ProjectState

import appkit_mantine as mn
from appkit_ui.components.dialogs import delete_dialog
from appkit_ui.global_states import LoadingState

MAX_TEAM_AVATARS = 4

SORTABLE_HEADER_STYLE = {
    **TABLE_HEADER_STYLE,
    "cursor": "pointer",
    "userSelect": "none",
}


def _sort_indicator(column: str) -> rx.Component:
    """Chevron showing the sort direction on the active column."""
    return rx.cond(
        ProjectState.sort_column == column,
        rx.cond(
            ProjectState.sort_desc,
            rx.icon("chevron-down", size=14),
            rx.icon("chevron-up", size=14),
        ),
        rx.fragment(),
    )


def _header(label: str, column: str = "", **props: Any) -> rx.Component:
    """Table header cell; clickable for sorting when a column key is given."""
    if not column:
        return mn.table.th(
            mn.text(label, size="sm", fw="800"), style=TABLE_HEADER_STYLE, **props
        )
    return mn.table.th(
        mn.group(
            mn.text(label, size="sm", fw="800"),
            _sort_indicator(column),
            gap="4px",
            wrap="nowrap",
            align="center",
        ),
        style=SORTABLE_HEADER_STYLE,
        on_click=ProjectState.toggle_sort(column),
        **props,
    )


def _project_name_cell(project: Project) -> rx.Component:
    """Project avatar with name and code."""
    return mn.group(
        project_initials(project),
        mn.stack(
            mn.text(
                project.name_de,
                size="sm",
                fw="700",
                c="var(--alloq-text)",
                lh="1.15",
                truncate=True,
            ),
            mn.text(project.code, size="xs", c="dimmed", lh="1"),
            gap="2px",
            style={"minWidth": 0},
        ),
        gap="md",
        align="center",
        wrap="nowrap",
    )


def _status_badge(project: Project) -> rx.Component:
    return mn.badge(
        project.state,
        color=status_color(project.state),
        variant="light",
        radius="xl",
        size="md",
        left_section=mn.text("●", size="8px"),
        style={"textTransform": "none", "fontWeight": "700"},
    )


def _period_cell(project: Project) -> rx.Component:
    return mn.text(
        rx.cond(project.start_date, format_date_de_named(project.start_date), "—")
        + " → "
        + rx.cond(project.end_date, format_date_de_named(project.end_date), "—"),
        size="sm",
        c="var(--alloq-text)",
        style=NO_WRAP_CELL_STYLE,
    )


def _progress_cell(project: Project) -> rx.Component:
    return mn.group(
        mn.progress(
            value=project.current_progress,
            color=rx.cond(project.risk_count > 0, "red", project.color),
            size="sm",
            radius="xl",
            w="6rem",
            bg="var(--alloq-meter-track)",
        ),
        de_number(value=project.current_progress, suffix="%"),
        gap="sm",
        align="center",
        wrap="nowrap",
    )


def _team_cell(project: Project) -> rx.Component:
    overflow = project.team_members.length() - MAX_TEAM_AVATARS
    return rx.cond(
        project.team_members.length() > 0,
        mn.avatar.group(
            rx.foreach(project.team_members[:MAX_TEAM_AVATARS], team_initial),
            rx.cond(
                overflow > 0,
                mn.avatar("+" + overflow.to_string(), size="sm", radius="lg"),
                rx.fragment(),
            ),
        ),
        mn.text("—", size="sm", c="dimmed"),
    )


def _risk_cell(project: Project) -> rx.Component:
    return rx.cond(
        project.risk_count > 0,
        mn.group(
            rx.icon("triangle-alert", size=14, color="var(--mantine-color-red-6)"),
            de_number(value=project.risk_count),
            gap="4px",
            wrap="nowrap",
            align="center",
        ),
        mn.text("—", size="sm", c="dimmed"),
    )


def _actions_cell(project: Project) -> rx.Component:
    return mn.group(
        mn.box(
            rx.icon_button(
                rx.icon("square-pen", size=16),
                variant="ghost",
                on_click=[
                    LoadingState.set_is_loading(True),
                    ProjectState.select_project_with_tab(project.id, "daten"),
                ],
            ),
            on_click=rx.stop_propagation,
        ),
        mn.box(
            delete_dialog(
                title="Projekt löschen",
                content=project.name_de,
                on_click=ProjectState.delete_project(project.id),
                icon_button=True,
                color="red",
                variant="subtle",
                size="sm",
            ),
            on_click=rx.stop_propagation,
        ),
        gap="12px",
        wrap="nowrap",
        align="center",
    )


def _project_table_row(project: Project) -> rx.Component:
    """Render a single project as a table row."""
    return mn.table.tr(
        mn.table.td(_project_name_cell(project)),
        mn.table.td(project.customer),
        mn.table.td(_status_badge(project)),
        mn.table.td(_period_cell(project)),
        mn.table.td(
            de_number(value=project.budget, suffix=" €"),
            style=NO_WRAP_CELL_STYLE,
            ta="right",
        ),
        mn.table.td(
            de_number(value=project.current_spent, suffix="%"),
            style=NO_WRAP_CELL_STYLE,
            ta="right",
        ),
        mn.table.td(_progress_cell(project), style=NO_WRAP_CELL_STYLE),
        mn.table.td(_team_cell(project)),
        mn.table.td(_risk_cell(project)),
        mn.table.td(_actions_cell(project), style=NO_WRAP_CELL_STYLE),
        style={"cursor": rx.cond(LoadingState.is_loading, "wait", "pointer")},
        on_click=[
            LoadingState.set_is_loading(True),
            ProjectState.select_project(project.id),
        ],
    )


def _table_head() -> rx.Component:
    return mn.table.thead(
        mn.table.tr(
            _header("Projekt", "name", width="280px"),
            _header("Kunde", "customer", width="160px"),
            _header("Status", "state", width="140px"),
            _header("Zeitraum", "start_date", width="220px"),
            _header("Budget", "budget", width="130px"),
            _header("Verbraucht", "current_spent", width="120px"),
            _header("Fortschritt", "current_progress", width="170px"),
            _header("Team", width="150px"),
            _header("Risiken", "risk_count", width="100px"),
            _header("", width="90px"),
        ),
    )


def _project_table_section(title: str, projects: rx.Var) -> rx.Component:
    """Titled table section; hidden when there are no projects."""
    return rx.cond(
        projects.length() > 0,
        mn.stack(
            mn.text(title, size="lg", fw="700"),
            mn.box(
                mn.table(
                    _table_head(),
                    mn.table.tbody(rx.foreach(projects, _project_table_row)),
                    sticky_header=True,
                    sticky_header_offset="0px",
                    striped=False,
                    highlight_on_hover=True,
                    highlight_on_hover_color="var(--alloq-surface-hover)",
                    w="100%",
                    miw="1570px",
                    style=TABLE_STYLE,
                ),
                width="100%",
                m="0",
                p="12px",
                style=TABLE_WRAPPER_STYLE,
            ),
            gap="sm",
        ),
    )


def project_table(empty_state: rx.Component) -> rx.Component:
    """Table view of all projects, split into 'my projects' and 'other projects'."""
    return rx.cond(
        ProjectState.is_loading,
        mn.center(
            rx.hstack(
                rx.spinner(size="3"),
                mn.text("Lade Projekte...", size="sm"),
                align="center",
                spacing="3",
            ),
            py="xl",
        ),
        rx.cond(
            (ProjectState.my_projects.length() == 0)
            & (ProjectState.other_projects.length() == 0),
            empty_state,
            mn.stack(
                _project_table_section("Meine Projekte", ProjectState.my_projects),
                _project_table_section("Weitere Projekte", ProjectState.other_projects),
                gap="xl",
            ),
        ),
    )
