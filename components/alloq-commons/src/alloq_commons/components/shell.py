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
from alloq_commons import theme
from alloq_commons.components.splash import SplashState, splash
from alloq_commons.components.toolbar import TOOLBAR_HEIGHT_PX
from alloq_commons.desktop import is_desktop
from appkit_ui.global_states import LoadingState
from appkit_user.authentication.templates import authenticated_page

SIDEBAR_WIDTH_PX = 244
PANE_GAP_PX = 8
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

_HIDDEN = f"html[{COLLAPSED_ATTR}]"
_NARROW = f"@media (max-width: {NARROW_PX - 1}px)"
_NATIVE = f"html[{theme.NATIVE_ATTR}]"

SHELL_CSS = (
    ".aq-window{display:flex;height:100dvh;overflow:hidden;}"
    f".aq-sidebar{{width:{SIDEBAR_WIDTH_PX}px;flex-shrink:0;overflow:hidden;"
    "display:flex;flex-direction:column;gap:14px;padding:16px 10px 12px;"
    "box-sizing:border-box;transition:width .22s ease,padding .22s ease,"
    "opacity .18s ease;}"
    f"{_HIDDEN} .aq-sidebar{{width:0;padding-left:0;padding-right:0;opacity:0;}}"
    f".aq-pane{{flex:1;min-width:0;margin:{PANE_GAP_PX}px {PANE_GAP_PX}px "
    f"{PANE_GAP_PX}px 0;display:flex;flex-direction:column;overflow:hidden;"
    f"border-radius:{theme.RADIUS};background:{theme.SURFACE};"
    f"box-shadow:{theme.PANE_SHADOW};transition:margin .22s ease;}}"
    f"{_HIDDEN} .aq-pane{{margin-left:{PANE_GAP_PX}px;}}"
    f".aq-toolbar{{height:{TOOLBAR_HEIGHT_PX}px;flex-shrink:0;display:flex;"
    "align-items:center;gap:16px;padding:0 14px 0 22px;"
    f"box-shadow:inset 0 -1px 0 {theme.BORDER};background:{theme.SURFACE};}}"
    ".aq-toolbar-title{min-width:0;flex-shrink:1;}"
    ".aq-toolbar-center{flex:1;display:flex;justify-content:center;min-width:0;}"
    ".aq-toolbar-actions{flex-shrink:0;}"
    ".aq-sidebar-reveal{display:none;margin-left:-8px;}"
    f"{_HIDDEN} .aq-sidebar-reveal{{display:flex;}}"
    # Traffic lights sit over the toolbar while the sidebar is hidden.
    f"{_NATIVE}[{COLLAPSED_ATTR}] .aq-toolbar{{padding-left:84px;}}"
    f".aq-scopebar{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;"
    f"padding:8px 22px;border-bottom:1px solid {theme.BORDER};"
    f"background:{theme.SURFACE};flex-shrink:0;}}"
    f".aq-body{{flex:1;min-height:0;overflow:auto;background:{theme.BACKGROUND};}}"
    ".aq-body[data-padded]{padding:22px 24px 28px;}"
    ".aq-body[data-flush]{display:flex;flex-direction:column;overflow:hidden;}"
    ".aq-body[data-flush]>*{flex:1;min-height:0;display:flex;"
    "flex-direction:column;}"
    f".aq-segmented{{background:{theme.token('segmented')};}}"
    ".aq-icon-btn{color:" + theme.TEXT_MUTED + ";}"
    f".aq-icon-btn[data-active=true]{{background:{theme.token('accent-soft')};"
    f"color:{theme.ACCENT};}}"
    ".aq-backdrop{display:none;}"
    f"{_NARROW}{{"
    ".aq-sidebar{position:fixed;inset:0 auto 0 0;z-index:300;"
    f"width:{SIDEBAR_WIDTH_PX}px !important;padding:16px 10px 12px !important;"
    f"opacity:1 !important;background:{theme.token('window-background')};"
    "transform:translateX(-100%);transition:transform .22s ease;"
    "box-shadow:0 0 40px rgba(0,0,0,.2);}"
    f"html[{OPEN_ATTR}] .aq-sidebar{{transform:none;}}"
    f"html[{OPEN_ATTR}] .aq-backdrop{{display:block;position:fixed;inset:0;"
    "z-index:299;background:rgba(0,0,0,.2);}"
    f".aq-pane{{margin:{PANE_GAP_PX}px !important;}}"
    ".aq-sidebar-reveal{display:flex;}"
    ".aq-toolbar{height:auto;min-height:52px;flex-wrap:wrap;padding:8px 12px;}"
    ".aq-toolbar-center{order:3;flex-basis:100%;justify-content:flex-start;"
    "overflow-x:auto;}"
    ".aq-body[data-padded]{padding:16px;}"
    "}"
    "@media (prefers-reduced-motion: reduce){.aq-sidebar,.aq-pane"
    "{transition:none !important;}}"
)


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
        rx.el.style(SHELL_CSS),
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
