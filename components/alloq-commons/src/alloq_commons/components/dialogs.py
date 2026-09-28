"""Typed wrappers around appkit_ui dialogs."""

from typing import Any, cast

import reflex as rx
from reflex.event import EventType

from appkit_ui.components.dialogs import delete_dialog as _appkit_delete_dialog


def delete_dialog(
    title: str,
    content: str | rx.Var | rx.Component,
    on_click: EventType[()],
    **kwargs: Any,
) -> rx.Component:
    """Delete confirmation dialog.

    appkit_ui annotates ``content`` as ``str`` and ``on_click`` as
    ``EventHandler``, but renders Vars/components and bound event specs fine.
    """
    return _appkit_delete_dialog(
        title,
        cast("str", content),
        cast("rx.EventHandler", on_click),
        **kwargs,
    )
