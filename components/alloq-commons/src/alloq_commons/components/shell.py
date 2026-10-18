"""App shell in the macOS style: translucent source-list sidebar on the left,
a floating white content pane with a toolbar on the right.

In the desktop window the native traffic lights sit on top of the sidebar
(title bar style "Overlay" in tauri.conf.json); the sidebar's top row stays
free for them and, like the toolbar, drags the window.

The sidebar collapses with ⌃⌘S (or ⌘\\) or the button in its title row (state in
sessionStorage, set on <html> before the first paint). Below 768px it becomes
a drawer over the pane.
"""

from collections.abc import Callable, Sequence
from typing import Any, cast

import reflex as rx
from reflex.event import EventType

import appkit_mantine as mn
from alloq_commons.components.splash import SplashState, splash
from alloq_commons.desktop import is_desktop
from appkit_ui.global_states import LoadingState
from appkit_user.authentication.templates import authenticated_page

NARROW_PX = 768
COLLAPSED_ATTR = "data-sidebar-collapsed"
OPEN_ATTR = "data-sidebar-open"
STORAGE_KEY = "alloq.sidebar.collapsed"

SIDEBAR_SCRIPT = (
    "(function(){var d=document.documentElement;"
    f"try{{if(sessionStorage.getItem('{STORAGE_KEY}')==='1')"
    f"d.setAttribute('{COLLAPSED_ATTR}','');}}catch(e){{}}"
    "window.aqToggleSidebar=function(){"
    f"if(window.matchMedia('(max-width: {NARROW_PX - 1}px)').matches){{"
    f"d.toggleAttribute('{OPEN_ATTR}');return;}}"
    f"var c=d.toggleAttribute('{COLLAPSED_ATTR}');"
    f"try{{sessionStorage.setItem('{STORAGE_KEY}',c?'1':'0');}}catch(e){{}}}};"
    f"window.aqCloseSidebar=function(){{d.removeAttribute('{OPEN_ATTR}');}};"
    "document.addEventListener('keydown',function(e){"
    "var k=(e.key||'').toLowerCase();"
    "if((e.metaKey&&e.ctrlKey&&k==='s')||((e.metaKey||e.ctrlKey)&&k==='\\\\'))"
    "{e.preventDefault();"
    "window.aqToggleSidebar();}});})();"
)
"""Head script: restores the collapsed state and binds ⌃⌘S (macOS standard,
also on German keyboards) and ⌘\\ / Ctrl+\\."""


def _loading_bar() -> rx.Component:
    return rx.box(
        class_name=rx.cond(
            LoadingState.is_loading, "rainbow-gradient-bar", "default-bar"
        ),
    )


def app_layout(
    sidebar: rx.Component,
    toolbar: rx.Component | None,
    content: rx.Component,
    *,
    scope: rx.Component | None = None,
    padded: bool = True,
) -> rx.Component:
    """Window: sidebar plus floating pane with toolbar and scrolling content.

    ``padded=False`` gives the content the full pane (lists, planning grid):
    it then manages its own scrolling.
    """
    body_attrs = {"data-padded": ""} if padded else {"data-flush": ""}
    return mn.box(
        _loading_bar(),
        mn.box(
            class_name="aq-backdrop",
            on_click=rx.call_script("window.aqCloseSidebar()"),
        ),
        sidebar,
        mn.box(
            toolbar if toolbar is not None else rx.fragment(),
            scope if scope is not None else rx.fragment(),
            mn.box(content, class_name="aq-body", custom_attrs=body_attrs),
            class_name="aq-pane",
            custom_attrs={"role": "main"},
        ),
        class_name="aq-window",
    )


def desktop_handlers(
    on_load: EventType[()] | Sequence[Any] | None,
) -> list[Any] | None:
    """Page handlers as a list; the desktop app ends them by hiding the splash."""
    if on_load is None:
        handlers: list[Any] = []
    elif isinstance(on_load, Sequence):
        handlers = list(on_load)
    else:
        handlers = [on_load]
    if is_desktop():
        handlers.append(SplashState.finish)
    return handlers or None


def app_page(
    route: str,
    title: str,
    sidebar: rx.Component,
    *,
    toolbar: rx.Component | None = None,
    scope: rx.Component | None = None,
    padded: bool = True,
    admin_only: bool = False,
    on_load: EventType[()] | Sequence[Any] | None = None,
) -> Callable[[Callable[[], rx.Component]], rx.Component]:
    """Authenticated page in the app shell.

    Registers the route through appkit's ``authenticated_page`` (session
    monitor, admin gate, loading state) with our window as template.
    """
    handlers = desktop_handlers(on_load)

    def template(content: rx.Component) -> rx.Component:
        window = app_layout(sidebar, toolbar, content, scope=scope, padded=padded)
        return rx.fragment(splash(), window) if is_desktop() else window

    return authenticated_page(
        route=route,
        title=title,
        template=template,
        admin_only=admin_only,
        on_load=cast("Any", handlers),
    )
