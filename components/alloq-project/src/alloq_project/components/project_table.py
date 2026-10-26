"""Project list (macOS table) with groups and the project inspector."""

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.formatters import de_number
from alloq_commons.components.list_view import (
    badge,
    cell_main,
    empty_list,
    list_group,
    list_header,
    list_row,
    meter,
    number,
    split_view,
    sticky_block_header,
)
from alloq_commons.models.project import Project
from alloq_project.components.project_inspector import project_inspector
from alloq_project.components.project_parts import period, project_tile, status_tone
from alloq_project.states.project_state import ProjectState
from reflex.vars import ArrayVar, ObjectVar

import appkit_mantine as mn
from appkit_ui.global_states import LoadingState

TEMPLATE = "minmax(160px, 2fr) 124px 160px 96px minmax(90px, 1fr) 52px"
COLUMNS: list[tuple[str, str, bool]] = [
    ("Projekt", "name", False),
    ("Status", "state", False),
    ("Zeitraum", "start_date", False),
    ("Bedarf", "total_pt", True),
    ("Verbraucht", "current_spent", False),
    ("Risiken", "risk_count", True),
]


def _row(project: ObjectVar[Project]) -> rx.Component:
    selected = ProjectState.inspected.to(Project).id == project.id
    return list_row(
        cell_main(project_tile(project), project.name_de, project.customer),
        rx.el.span(badge(project.state, status_tone(project.state))),
        number(period(project), right=False, color=theme.TEXT_MUTED),
        number(
            de_number(value=project.total_pt, suffix=" PT"),
            fontWeight="600",
        ),
        mn.group(
            meter(project.current_spent),
            number(project.current_spent.to(str) + " %", minWidth="38px"),
            gap=8,
            wrap="nowrap",
        ),
        number(
            rx.cond(project.risk_count > 0, project.risk_count.to(str), "–"),
            color=rx.cond(project.risk_count > 0, theme.NEGATIVE, theme.TEXT_MUTED),
            fontWeight=rx.cond(project.risk_count > 0, "600", "400"),
        ),
        template=TEMPLATE,
        selected=selected,
        on_click=ProjectState.inspect(project.id),
        on_double_click=[
            LoadingState.set_is_loading(True),
            ProjectState.select_project(project.id),
        ],
    )


def _group(title: str, rows: ArrayVar) -> rx.Component:
    return rx.cond(
        rows.length() > 0,
        mn.box(
            list_group(
                title,
                rows.length(),
                style=sticky_block_header("30px"),
            ),
            rx.foreach(rows, _row),
        ),
        rx.fragment(),
    )


def _total_row() -> rx.Component:
    return rx.el.div(
        rx.el.span("Summe", style={"gridColumn": "span 3"}),
        number(de_number(value=ProjectState.visible_total_pt, suffix=" PT")),
        rx.fragment(),
        rx.fragment(),
        class_name="aq-tfoot",
        style={"gridTemplateColumns": TEMPLATE},
        custom_attrs={"role": "row"},
    )


def project_list() -> rx.Component:
    return mn.box(
        list_header(
            COLUMNS,
            TEMPLATE,
            sort_column=ProjectState.sort_column,
            sort_desc=ProjectState.sort_desc,
            on_sort=ProjectState.toggle_sort,
        ),
        _group("Meine Projekte", ProjectState.mine_rows),
        _group("Weitere Projekte", ProjectState.other_rows),
        _group("Geplant", ProjectState.planned_rows),
        _group("Interne Projekte", ProjectState.internal_rows),
        _group("Abgeschlossen", ProjectState.closed_rows),
        rx.cond(
            ProjectState.row_count == 0,
            empty_list("Keine Projekte mit diesem Filter."),
            rx.fragment(),
        ),
        _total_row(),
    )


def project_table(empty_state: rx.Component) -> rx.Component:
    """List view of all projects with the inspector on the right."""
    return rx.cond(
        ProjectState.is_loading & (ProjectState.projects.length() == 0),
        mn.center(mn.loader(size="sm"), py="xl", flex="1"),
        rx.cond(
            ProjectState.projects.length() == 0,
            empty_state,
            split_view(
                project_list(),
                project_inspector(),
                show_inspector=ProjectState.show_inspector,
            ),
        ),
    )
