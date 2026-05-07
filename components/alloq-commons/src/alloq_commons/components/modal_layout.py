"""Shared modal/drawer layout primitives.

Provides consistent structure, sticky footer, and CSS-class-driven theming
so that all modals and drawers share the same visual language.
"""

import reflex as rx

import appkit_mantine as mn

# CSS class applied to mn.modal / mn.drawer for unified styling.
MODAL_CLASS = "alloq-modal"
DRAWER_CLASS = "alloq-drawer"


def modal_footer(
    submit_label: str,
    on_cancel: rx.EventHandler,
    *,
    disabled: bool | rx.Var[bool] = False,
    loading: bool | rx.Var[bool] = False,
) -> rx.Component:
    """Sticky footer with cancel + submit buttons for modals/drawers."""
    return mn.group(
        mn.button(
            "Abbrechen",
            variant="subtle",
            on_click=on_cancel,
        ),
        mn.button(
            submit_label,
            type="submit",
            disabled=disabled,
            loading=loading,
            px="xl",
        ),
        justify="end",
        class_name="alloq-modal-footer",
    )


def modal_form_layout(
    content: rx.Component,
    footer: rx.Component,
    on_submit: rx.EventHandler,
    *,
    reset_on_submit: bool = False,
) -> rx.Component:
    """Form layout with scrollable body and fixed footer.

    Wraps content in rx.form.root with a flex column: scrollable body on top,
    sticky footer pinned to the bottom.
    """
    return rx.form.root(
        rx.flex(
            rx.box(
                content,
                class_name="alloq-modal-scroll",
            ),
            footer,
            direction="column",
            class_name="alloq-modal-inner",
        ),
        on_submit=on_submit,
        reset_on_submit=reset_on_submit,
        height="100%",
        class_name="alloq-modal-form",
    )
