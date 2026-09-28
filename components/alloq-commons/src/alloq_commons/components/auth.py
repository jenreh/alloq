"""Typed wrapper around the appkit_user page template."""

from collections.abc import Callable, Sequence
from typing import Any, cast

import reflex as rx
from reflex.event import EventType

from appkit_user.authentication.templates import (
    authenticated as _appkit_authenticated,
)


def authenticated(
    route: str | None = None,
    title: str | None = None,
    navbar: rx.Component | None = None,
    *,
    with_header: bool = True,
    admin_only: bool = False,
    # Handlers with defaulted args (e.g. ``State.load``) are valid on_load events.
    on_load: EventType[()] | Sequence[Any] | None = None,
) -> Callable[[Callable[[], rx.Component]], rx.Component]:
    """Authenticated page template.

    appkit_user annotates ``on_load`` as ``EventHandler``, but it accepts
    bound event specs such as ``State.handler(arg)`` just as well.
    """
    handlers = list(on_load) if isinstance(on_load, Sequence) else on_load
    return _appkit_authenticated(
        route=route,
        title=title,
        navbar=navbar,
        with_header=with_header,
        admin_only=admin_only,
        on_load=cast("Any", handlers),
    )
