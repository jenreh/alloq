"""Team list (macOS table) with groups and the employee inspector."""

import reflex as rx
from alloq_commons.components.formatters import de_number
from alloq_commons.components.list_view import (
    cell_main,
    empty_list,
    list_group,
    list_header,
    list_row,
    meter,
    number,
    split_view,
    sticky_block_header,
    tag,
)
from alloq_team.components.employee_inspector import employee_inspector
from alloq_team.components.employee_parts import (
    employee_avatar,
    load_label,
    tone_color,
)
from alloq_team.states.team_list_state import TeamDetail
from alloq_team.states.team_state import TeamState
from reflex.vars import ArrayVar, ObjectVar

import appkit_mantine as mn
from appkit_ui.global_states import LoadingState

TEMPLATE = "minmax(200px, 2fr) 110px 48px minmax(130px, 1fr) 70px 64px"
COLUMNS: list[tuple[str, str, bool]] = [
    ("Name", "name", False),
    ("Rolle", "role", False),
    ("h/W", "hours", True),
    ("Auslastung 8 W.", "load_percent", False),
    ("Frei 8 W.", "free_days", True),
    ("Projekte", "project_count", True),
]


def _row(row: ObjectVar[TeamDetail]) -> rx.Component:
    return list_row(
        cell_main(employee_avatar(row), row.name, row.subtitle),
        rx.el.span(rx.cond(row.role != "", tag(row.role), rx.fragment())),
        number(row.hours),
        mn.group(
            meter(
                rx.cond(row.absent_now, 0, row.load_percent), tone_color(row.load_tone)
            ),
            number(
                load_label(row),
                minWidth="56px",
                color=tone_color(row.load_tone),
                fontWeight=rx.cond(row.load_tone == "negative", "600", "400"),
            ),
            gap=8,
            wrap="nowrap",
        ),
        number(
            de_number(
                value=row.free_days,
                suffix=" PT",
                decimal_scale=1,
                fixed_decimal_scale=True,
            ),
            fontWeight="600",
        ),
        number(row.project_count),
        template=TEMPLATE,
        selected=TeamState.inspected.to(TeamDetail).id == row.id,
        on_click=TeamState.inspect(row.id),
        on_double_click=[
            LoadingState.set_is_loading(True),
            TeamState.select_employee(row.id),
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
        rx.el.span("Summe", style={"gridColumn": "span 4"}),
        number(
            de_number(
                value=TeamState.visible_total_free_days,
                suffix=" PT",
                decimal_scale=1,
                fixed_decimal_scale=True,
            ),
            fontWeight="600",
        ),
        rx.fragment(),
        class_name="aq-tfoot",
        style={"gridTemplateColumns": TEMPLATE},
        custom_attrs={"role": "row"},
    )


def employee_list() -> rx.Component:
    return mn.box(
        list_header(
            COLUMNS,
            TEMPLATE,
            sort_column=TeamState.sort_column,
            sort_desc=TeamState.sort_desc,
            on_sort=TeamState.toggle_sort,
        ),
        _group("Meine Mitarbeiter", TeamState.mine_rows),
        _group("Weitere Mitarbeiter", TeamState.other_rows),
        _group("Weitere Abteilungen", TeamState.unhighlighted_rows),
        rx.cond(
            TeamState.row_count == 0,
            empty_list("Keine Mitarbeiter mit diesem Filter."),
            rx.fragment(),
        ),
        _total_row(),
    )


def employee_table() -> rx.Component:
    """List view of the team with the inspector on the right."""
    return rx.cond(
        TeamState.is_loading & (TeamState.employees.length() == 0),
        mn.center(mn.loader(size="sm"), py="xl", flex="1"),
        split_view(
            employee_list(),
            employee_inspector(),
            show_inspector=TeamState.show_inspector,
        ),
    )
