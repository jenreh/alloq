import reflex as rx

import appkit_mantine as mn
from alloq_commons.services.quick_project import MAX_CODE_LENGTH


def quick_project_fields(
    *,
    name_value: str | rx.Var[str],
    on_name_change: rx.EventHandler,
    code_value: str | rx.Var[str],
    on_code_change: rx.EventHandler,
    on_create: rx.EventHandler,
    loading: bool | rx.Var[bool],
) -> rx.Component:
    """Inline name/code inputs for creating a project without leaving a modal."""
    return mn.stack(
        mn.text_input(
            label="Projektname",
            placeholder="Name des neuen Projekts",
            value=name_value,
            on_change=on_name_change,
            left_section=rx.icon("folder-plus", size=16),
        ),
        mn.group(
            mn.text_input(
                label="Kürzel",
                placeholder=f"max. {MAX_CODE_LENGTH} Zeichen",
                value=code_value,
                on_change=on_code_change,
                maxlength=MAX_CODE_LENGTH,
                flex="1",
            ),
            mn.button(
                "Anlegen",
                type="button",
                variant="light",
                on_click=on_create,
                loading=loading,
            ),
            align="flex-end",
            gap="sm",
            w="100%",
        ),
        gap="sm",
        w="100%",
        p="sm",
        style={
            "border": "1px solid var(--alloq-border-strong)",
            "borderRadius": "6px",
        },
    )


def section(*children: rx.Component) -> rx.Component:
    """White grouped content section for the employee detail drawer."""
    return rx.box(
        mn.stack(
            *children,
            gap="md",
            w="100%",
        ),
        width="100%",
        padding="18px",
        background="var(--alloq-fade-bg)",
        border_radius="8px",
        box_shadow="0 8px 24px rgba(0, 0, 0, 0.04)",
    )
