from typing import Any

import reflex as rx
from reflex.event import EventType
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_commons.components.dialogs import delete_dialog
from alloq_commons.components.forms import section
from alloq_commons.components.modal_layout import (
    MODAL_CLASS,
    modal_footer,
    modal_form_layout,
)
from alloq_commons.components.toolbar import primary_button, toolbar_search
from alloq_commons.models import Department
from alloq_commons.state.department_states import DepartmentState
from appkit_ui.styles import sticky_header_style


def department_form_fields(
    department: ObjectVar[Department] | None = None,
) -> rx.Component:
    """Form fields for the department add/edit dialogs."""
    is_edit_mode = department is not None
    return section(
        mn.text_input(
            name="name",
            label="Name",
            description="Eindeutiger Name der Abteilung.",
            default_value=department.name if is_edit_mode else "",  # type: ignore[union-attr]
            required=True,
            custom_attrs={"maxLength": 255},
            left_section=rx.icon("building-2", size=16),
        ),
        mn.text_input(
            name="abbreviation",
            label="Kürzel",
            description="Eindeutiges Kürzel (max. 10 Zeichen), z.B. IT.",
            default_value=department.abbreviation if is_edit_mode else "",  # type: ignore[union-attr]
            required=True,
            custom_attrs={"maxLength": 10},
        ),
        mn.switch(
            name="highlighted",
            label="Abteilung hervorheben",
            description="Mitarbeiter erscheinen in den hervorgehobenen Bereichen.",
            default_checked=department.highlighted if is_edit_mode else False,  # type: ignore[union-attr]
        ),
    )


def _department_modal(
    *,
    title: str,
    opened: bool | rx.Var,
    on_close: EventType[()],
    on_submit: EventType[Any],
    submit_label: str,
    content: rx.Component,
) -> rx.Component:
    return mn.modal(
        modal_form_layout(
            content=mn.flex(
                content,
                mn.space(height="2rem"),
                direction="column",
                width="100%",
            ),
            footer=modal_footer(submit_label, on_close),
            on_submit=on_submit,
        ),
        title=title,
        opened=opened,
        on_close=on_close,
        size="md",
        centered=True,
        class_name=MODAL_CLASS,
        overlay_props={"backgroundOpacity": 0.5, "blur": 4},
    )


def add_department_modal() -> rx.Component:
    return _department_modal(
        title="Abteilung hinzufügen",
        opened=DepartmentState.add_modal_open,
        on_close=DepartmentState.close_add_modal,
        on_submit=DepartmentState.create_department,
        submit_label="Abteilung speichern",
        content=department_form_fields(),
    )


def edit_department_modal() -> rx.Component:
    return _department_modal(
        title="Abteilung bearbeiten",
        opened=DepartmentState.edit_modal_open,
        on_close=DepartmentState.close_edit_modal,
        on_submit=DepartmentState.update_department,
        submit_label="Abteilung aktualisieren",
        content=department_form_fields(
            DepartmentState.selected_department.to(Department)
        ),
    )


def departments_table_row(department: ObjectVar[Department]) -> rx.Component:
    return mn.table.tr(
        mn.table.td(
            mn.text(department.name, size="sm", fw="500"),
        ),
        mn.table.td(
            mn.text(department.abbreviation, size="sm", c="dimmed"),
        ),
        mn.table.td(
            mn.text(
                rx.cond(department.highlighted, "Hervorgehoben", "–"),
                size="sm",
                c=rx.cond(department.highlighted, "blue", "dimmed"),
            ),
        ),
        mn.table.td(
            mn.group(
                rx.icon_button(
                    rx.icon("square-pen", size=16),
                    on_click=DepartmentState.select_department_and_open_edit(
                        department.id
                    ),
                    variant="ghost",
                ),
                delete_dialog(
                    title="Löschen bestätigen",
                    content=department.name,
                    on_click=DepartmentState.delete_department(department.id),
                    icon_button=True,
                    color="red",
                    variant="subtle",
                ),
                gap="xs",
                wrap="nowrap",
                align="center",
            ),
            width="1%",
            style={"whiteSpace": "nowrap"},
        ),
    )


def _loading_row() -> rx.Component:
    return mn.table.tr(
        mn.table.td(
            rx.hstack(
                rx.spinner(size="3"),
                mn.text("Lade Abteilungen...", size="sm"),
                align="center",
                justify="center",
                spacing="3",
            ),
            col_span=4,
            style={"textAlign": "center"},
        ),
    )


def departments_table() -> rx.Component:
    """Full CRUD interface for departments."""
    return mn.stack(
        add_department_modal(),
        edit_department_modal(),
        mn.table(
            mn.table.thead(
                mn.table.tr(
                    mn.table.th(mn.text("Name", size="sm", fw="700")),
                    mn.table.th(mn.text("Kürzel", size="sm", fw="700")),
                    mn.table.th(mn.text("Hervorhebung", size="sm", fw="700")),
                    mn.table.th(mn.text("", size="sm")),
                    style=sticky_header_style,
                ),
            ),
            mn.table.tbody(
                rx.cond(
                    DepartmentState.is_loading,
                    _loading_row(),
                    rx.foreach(
                        DepartmentState.filtered_departments,
                        departments_table_row,
                    ),
                )
            ),
            sticky_header=True,
            sticky_header_offset="0px",
            highlight_on_hover=True,
            highlight_on_hover_color=rx.color_mode_cond(
                light="gray.0",
                dark="dark.8",
            ),
            w="100%",
        ),
        w="100%",
    )


def departments_toolbar() -> list[rx.Component]:
    """Toolbar actions of the department page."""
    return [
        toolbar_search(
            DepartmentState.search_filter,
            DepartmentState.set_search_filter,
            "Abteilungen suchen",
        ),
        primary_button("Neue Abteilung", "plus", DepartmentState.open_add_modal),
    ]
