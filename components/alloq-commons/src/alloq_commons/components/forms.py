import reflex as rx

import appkit_mantine as mn


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
        # border="1px solid var(--alloq-border)",
        border_radius="8px",
        box_shadow="0 8px 24px rgba(91, 76, 34, 0.05)",
    )
