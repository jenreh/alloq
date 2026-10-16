import reflex as rx
from reflex.event import EventCallback

import appkit_mantine as mn
from alloq_commons.models.view_mode import VIEW_MODE_GRID, VIEW_MODE_TABLE


def _icon_label(icon: str, label: str) -> rx.Component:
    return mn.center(
        rx.icon(icon, size=15, stroke_width=1.8),
        title=label,
        aria_label=label,
        h=18,
    )


def view_mode_toggle(
    view_mode: rx.Var[str] | str,
    on_change: EventCallback[str],
) -> rx.Component:
    """Segmented switch between list and card view."""
    return mn.segmented_control(
        data=[
            {"value": VIEW_MODE_TABLE, "label": _icon_label("list", "Liste")},
            {"value": VIEW_MODE_GRID, "label": _icon_label("layout-grid", "Kacheln")},
        ],
        value=view_mode,
        on_change=on_change,
        size="xs",
        radius="md",
        class_name="aq-segmented",
    )
