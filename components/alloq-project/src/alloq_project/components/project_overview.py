import reflex as rx
from alloq_commons.models.project import RequiredCapacity
from alloq_project.components.project_card import project_card
from alloq_project.components.project_form import (
    form_footer,
    form_layout,
    project_form_fields,
)
from alloq_project.states.project_state import ProjectState, ProjectValidationState

import appkit_mantine as mn


def add_project_modal() -> rx.Component:
    """Modal for creating a new project."""
    return mn.modal(
        form_layout(
            content=mn.flex(
                project_form_fields(),
                mn.space(height="1.5rem"),
                direction="column",
                width="100%",
                key=ProjectValidationState.form_version.to(str),
            ),
            footer=form_footer(
                "Projekt speichern",
                ProjectState.close_add_modal,
                disabled=ProjectValidationState.is_form_invalid,
            ),
            on_submit=ProjectState.create_project,
        ),
        title="Neues Projekt",
        opened=ProjectState.add_modal_open,
        on_close=ProjectState.close_add_modal,
        size="lg",
        centered=True,
        class_name="alloq-project-detail-modal",
        overlay_props={"backgroundOpacity": 0.5, "blur": 4},
    )


def _required_capacity_row(capacity: RequiredCapacity) -> rx.Component:
    """Render one required capacity row in the detail drawer."""
    return mn.group(
        mn.text(capacity.role_name, size="sm", fw="700"),
        mn.badge(
            capacity.person_days.to_string() + " PD",
            variant="light",
            radius="sm",
            color="yellow",
            style={
                "backgroundColor": "var(--alloq-tag-bg)",
                "color": "var(--alloq-accent-strong)",
                "textTransform": "none",
                "fontWeight": "bold",
            },
        ),
        justify="space-between",
        w="100%",
        style={
            "backgroundColor": "var(--alloq-item-bg, var(--alloq-surface-muted))",
            "padding": "8px 12px",
            "borderRadius": "6px",
        },
    )


def project_detail_drawer() -> rx.Component:
    """Right-side drawer for editing project details."""
    return mn.drawer(
        form_layout(
            content=mn.flex(
                project_form_fields(),
                mn.space(height="1.5rem"),
                direction="column",
                width="100%",
                key=ProjectValidationState.form_version.to(str),
            ),
            footer=form_footer(
                "Projekt aktualisieren",
                ProjectState.close_detail_drawer,
                disabled=ProjectValidationState.is_form_invalid,
            ),
            on_submit=ProjectState.update_project,
        ),
        title=rx.cond(
            ProjectState.selected_project,
            ProjectState.selected_project.name_de,
            "Projekt Details",
        ),
        opened=ProjectState.detail_drawer_open,
        on_close=ProjectState.close_detail_drawer,
        position="right",
        size="lg",
        overlay_props={"backgroundOpacity": 0.3, "blur": 3},
        offset="15px",
        radius="md",
        class_name="alloq-project-detail-drawer",
        with_close_button=True,
        close_on_click_outside=True,
    )


def _project_section(title: str, projects: rx.Var) -> rx.Component:
    """Helper to render a titled section of project cards."""
    return rx.cond(
        projects.length() > 0,
        mn.stack(
            mn.text(
                title,
                size="lg",
                fw="700",
            ),
            mn.flex(
                rx.foreach(projects, project_card),
                wrap="wrap",
                gap="md",
                direction="row",
                justify="flex-start",
                align="flex-start",
            ),
            gap="sm",
        ),
    )


def project_grid() -> rx.Component:
    """Grid view of all projects, split into 'my projects' and 'other projects'."""
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
        mn.stack(
            _project_section("Meine Projekte", ProjectState.my_projects),
            _project_section("Weitere Projekte", ProjectState.other_projects),
            gap="xl",
        ),
    )


def project_overview() -> rx.Component:
    """Complete project overview component."""
    return mn.stack(
        add_project_modal(),
        project_detail_drawer(),
        project_grid(),
        gap="md",
        width="100%",
    )
