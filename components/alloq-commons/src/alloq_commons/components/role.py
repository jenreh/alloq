import reflex as rx

import appkit_mantine as mn
from alloq_commons.models import Role
from alloq_commons.state.role_states import RoleState
from appkit_ui.components.dialogs import delete_dialog
from appkit_ui.components.form_inputs import hidden_field
from appkit_ui.styles import sticky_header_style


def role_form_fields(role: Role | None = None) -> rx.Component:
    """Reusable form fields for role add/edit dialogs."""
    is_edit_mode = role is not None

    return mn.flex(
        hidden_field(
            name="role_id",
            default_value=(
                role.id.to_string() if is_edit_mode else ""  # type: ignore[union-attr]
            ),
        ),
        mn.text_input(
            name="name",
            label="Name",
            description="Eindeutiger Name der Rolle (max. 255 Zeichen).",
            default_value=role.name if is_edit_mode else "",
            required=True,
            max_length=255,
            left_section=rx.icon("shield", size=16),
        ),
        mn.textarea(
            name="description",
            label="Beschreibung",
            description="Optionale Beschreibung der Rolle.",
            default_value=role.description if is_edit_mode else "",
            required=False,
            auto_size=True,
            min_rows=3,
            max_rows=6,
        ),
        direction="column",
        gap="md",
        width="100%",
    )


def _modal_footer(
    submit_label: str,
    on_cancel: rx.EventHandler,
) -> rx.Component:
    """Footer buttons for add/edit modals."""
    return rx.flex(
        mn.button(
            "Abbrechen",
            variant="subtle",
            on_click=on_cancel,
        ),
        mn.button(
            submit_label,
            type="submit",
            loading=RoleState.is_loading,
        ),
        direction="row",
        gap="9px",
        justify_content="end",
        padding="16px",
        border_top="1px solid var(--mantine-color-default-border)",
        background="var(--mantine-color-body)",
        width="100%",
    )


def _role_modal(
    title: str,
    opened: bool | rx.Var,
    on_close: rx.EventHandler,
    on_submit: rx.EventHandler,
    submit_label: str,
    content: rx.Component,
) -> rx.Component:
    """Shared modal structure for add/edit role."""
    return mn.modal(
        rx.form.root(
            rx.flex(
                rx.box(
                    content,
                    flex="1",
                    min_height="0",
                    width="100%",
                    padding="md",
                ),
                _modal_footer(submit_label, on_close),
                direction="column",
                height="100%",
                width="100%",
            ),
            on_submit=on_submit,
            reset_on_submit=False,
            height="100%",
        ),
        title=title,
        opened=opened,
        on_close=on_close,
        size="md",
        centered=True,
        overlay_props={"backgroundOpacity": 0.5, "blur": 4},
    )


def add_role_modal() -> rx.Component:
    """Modal for adding a new role."""
    return _role_modal(
        title="Rolle hinzufügen",
        opened=RoleState.add_modal_open,
        on_close=RoleState.close_add_modal,
        on_submit=RoleState.create_role,
        submit_label="Rolle speichern",
        content=role_form_fields(),
    )


def edit_role_modal() -> rx.Component:
    """Modal for editing an existing role."""
    return _role_modal(
        title="Rolle bearbeiten",
        opened=RoleState.edit_modal_open,
        on_close=RoleState.close_edit_modal,
        on_submit=RoleState.update_role,
        submit_label="Rolle aktualisieren",
        content=role_form_fields(role=RoleState.selected_role),
    )


def add_role_button(
    label: str = "Rolle hinzufügen",
    icon: str = "plus",
    icon_size: int = 16,
    **kwargs,
) -> rx.Component:
    """Button to open the add role modal."""
    return mn.button(
        label,
        left_section=rx.icon(icon, size=icon_size),
        on_click=RoleState.open_add_modal,
        **kwargs,
    )


def update_role_button(
    role: Role,
    icon: str = "square-pen",
    icon_size: int = 16,
    **kwargs,
) -> rx.Component:
    """Icon button to open the edit modal for a role."""
    return rx.icon_button(
        rx.icon(icon, size=icon_size),
        on_click=lambda: RoleState.select_role_and_open_edit(role.id),
        **kwargs,
    )


def delete_role_button(role: Role, **kwargs) -> rx.Component:
    """Delete button with confirmation dialog."""
    return delete_dialog(
        title="Löschen bestätigen",
        content=rx.cond(role.name, role.name, "Unbekannte Rolle"),
        on_click=lambda: RoleState.delete_role(role.id),
        icon_button=True,
        color="red",
        **kwargs,
    )


def roles_table_row(role: Role) -> rx.Component:
    """Render a single role as a table row."""
    return mn.table.tr(
        mn.table.td(
            mn.text(role.name, size="sm", fw="500", style={"whiteSpace": "nowrap"}),
        ),
        mn.table.td(
            mn.text(
                role.description,
                size="sm",
                c="dimmed",
                style={
                    "whiteSpace": "nowrap",
                    "overflow": "hidden",
                    "textOverflow": "ellipsis",
                    "maxWidth": "400px",
                },
            ),
        ),
        mn.table.td(
            mn.group(
                update_role_button(role=role, variant="ghost"),
                delete_role_button(role=role, variant="subtle"),
                gap="xs",
                wrap="nowrap",
                align="center",
            ),
            width="1%",
            style={"whiteSpace": "nowrap"},
        ),
    )


def loading() -> rx.Component:
    """Loading indicator for the roles table."""
    return mn.table.tr(
        mn.table.td(
            rx.hstack(
                rx.spinner(size="3"),
                mn.text("Lade Rollen...", size="sm"),
                align="center",
                justify="center",
                spacing="3",
            ),
            col_span=3,
            style={"textAlign": "center"},
        ),
    )


def roles_table() -> rx.Component:
    """Full CRUD interface for organizational roles."""
    return mn.stack(
        add_role_modal(),
        edit_role_modal(),
        rx.flex(
            add_role_button(),
            mn.text_input(
                placeholder="Rollen suchen...",
                left_section=rx.icon("search", size=16),
                left_section_pointer_events="none",
                value=RoleState.search_filter,
                on_change=RoleState.set_search_filter,
                size="sm",
                w="18rem",
            ),
            rx.spacer(),
            width="100%",
            margin_bottom="md",
            gap="12px",
            align="center",
        ),
        mn.table(
            mn.table.thead(
                mn.table.tr(
                    mn.table.th(mn.text("Name", size="sm", fw="700")),
                    mn.table.th(mn.text("Beschreibung", size="sm", fw="700")),
                    mn.table.th(mn.text("", size="sm")),
                    style=sticky_header_style,
                ),
            ),
            mn.table.tbody(
                rx.cond(
                    RoleState.is_loading,
                    loading(),
                    rx.foreach(
                        RoleState.filtered_roles,
                        roles_table_row,
                    ),
                )
            ),
            sticky_header=True,
            sticky_header_offset="0px",
            striped=False,
            highlight_on_hover=True,
            highlight_on_hover_color=rx.color_mode_cond(
                light="gray.0",
                dark="dark.8",
            ),
            w="100%",
        ),
        w="100%",
        on_mount=RoleState.load_roles,
    )
