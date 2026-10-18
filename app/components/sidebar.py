"""Source-list sidebar of the app window (macOS style).

Top row free for the native traffic lights, then logo, planning, role capacity,
administration (admins only), and the signed-in user at the bottom.
"""

from typing import Any, Final, cast

import reflex as rx
from alloq_commons import theme
from alloq_commons.access import editor_only, viewer_only
from alloq_commons.components.formatters import de_number
from alloq_commons.components.toolbar import DRAG, SIDEBAR_TOGGLE_SCRIPT, icon_button
from alloq_commons.desktop import is_desktop
from alloq_dashboard.models import FreeCapacityKpi
from alloq_dashboard.states import RoleCapacityState
from reflex.style import set_color_mode
from reflex.vars import ObjectVar
from reflex_base.constants import LiteralColorMode

import appkit_mantine as mn
from appkit_ui.global_states import LoadingState
from appkit_user.authentication.backend.models import User
from appkit_user.authentication.components.components import requires_admin
from appkit_user.authentication.states import LoginState

from app.components.sidebar_state import SidebarState
from app.desktop.login_state import DesktopLoginState

PROJECTS_ROUTE: Final = "/projects"
TEAM_ROUTE: Final = "/team"

PLAN_ROUTE: Final = "/plan"

PLANNING_ITEMS: Final[list[tuple[str, str, str]]] = [
    ("/dashboard", "Übersicht", "layout-dashboard"),
    (PLAN_ROUTE, "Ressourcenplanung", "calendar-range"),
    (PROJECTS_ROUTE, "Projekte", "folder-kanban"),
    (TEAM_ROUTE, "Team", "users"),
]
ADMIN_ITEMS: Final[list[tuple[str, str, str]]] = [
    ("/admin/users", "Benutzer", "user-cog"),
    ("/admin/roles", "Rollen", "shield"),
    ("/admin/departments", "Abteilungen", "building-2"),
    ("/admin/holidays", "Feiertage", "calendar-days"),
]
VIEWER_ROUTES: Final = frozenset({PLAN_ROUTE, PROJECTS_ROUTE})
"""Pages the employee role may read; the other planning pages need edit rights
(admin or project manager)."""
_COUNTS: Final[dict[str, Any]] = {
    PROJECTS_ROUTE: SidebarState.project_count,
    TEAM_ROUTE: SidebarState.employee_count,
}
# appkit_user declares ``user`` as a plain field; class access yields a Var.
_USER = cast("ObjectVar[User]", LoginState.user)

ROW: Final = {
    "display": "flex",
    "alignItems": "center",
    "gap": "9px",
    "height": "30px",
    "padding": "0 10px",
    "borderRadius": "7px",
    "color": theme.SIDEBAR_TEXT,
    "textDecoration": "none",
    "cursor": "default",
    "fontSize": "13px",
}
SIGN_OUT: Final = DesktopLoginState.sign_out if is_desktop() else LoginState.logout
"""`logout` ends the session; the desktop app also forgets the Microsoft
account and its DB connections."""
NO_HOVER: Final = {"color": theme.SIDEBAR_TEXT}
"""Source lists don't recolor on hover; rx.link would turn the text blue."""


def is_route_active(url: str) -> rx.Var[bool]:
    """Whether the current page is ``url`` or its homepage alias."""
    current = rx.State.router.page.path
    if url in ("/", "/index"):
        return (current == "/") | (current == "/index")
    if url == "/plan":
        return (current == url) | (current == "/") | (current == "/index")
    return current == url


def _window_row() -> rx.Component:
    """Free space for the native window buttons, plus the collapse button."""
    return mn.group(
        mn.box(flex="1", h=20, custom_attrs=DRAG),
        icon_button(
            "panel-left-close",
            "Seitenleiste ausblenden (⌃⌘S)",
            rx.call_script(SIDEBAR_TOGGLE_SCRIPT),
        ),
        h=20,
        gap=0,
        wrap="nowrap",
        custom_attrs=DRAG,
    )


def _brand() -> rx.Component:
    return mn.group(
        mn.center(
            mn.image(src=rx.asset("img/alloq_icon.svg"), w=20, h=20, fit="contain"),
            w=30,
            h=30,
            style={
                "borderRadius": "8px",
                "backgroundColor": theme.SURFACE,
                "boxShadow": (
                    "0 0 0 0.5px rgba(0,0,0,0.1), 0 1px 3px rgba(0,0,0,0.08)"
                ),
                "flexShrink": "0",
            },
        ),
        mn.stack(
            mn.text("alloq", fz="14px", fw=600, c=theme.SIDEBAR_TEXT),
            mn.text("Ressourcenplanung", fz="11.5px", c=theme.SIDEBAR_MUTED),
            gap=0,
            miw=0,
        ),
        gap=10,
        px=6,
        wrap="nowrap",
        custom_attrs=DRAG,
    )


def _section(title: str, *rows: rx.Component) -> rx.Component:
    return mn.stack(
        mn.text(title, fz="11px", fw=600, c=theme.SIDEBAR_MUTED, px=10, pb=4),
        *rows,
        gap=1,
    )


def _count(value: Any, *, alert: Any = False) -> rx.Component:
    return mn.text(
        value,
        fz="12px",
        fw=rx.cond(alert, 600, 400),
        c=rx.cond(alert, theme.NEGATIVE, theme.SIDEBAR_MUTED),
        style=theme.NUMERIC,
    )


def _nav_item(route: str, label: str, icon: str) -> rx.Component:
    children = [
        rx.icon(icon, size=16, stroke_width=1.8, color=theme.ACCENT),
        mn.text(label, flex="1", miw=0, truncate="end"),
    ]
    if (count := _COUNTS.get(route)) is not None:
        children.append(rx.cond(count, _count(count), rx.fragment()))
    return rx.link(
        *children,
        href=route,
        underline="none",
        on_click=LoadingState.set_is_loading(True),
        class_name="aq-nav-item",
        _hover=NO_HOVER,
        aria_current=rx.cond(is_route_active(route), "page", None),
        style=ROW,
    )


def _guarded_nav_item(route: str, label: str, icon: str) -> rx.Component:
    """Nav item shown only to users who may open its page."""
    guard = viewer_only if route in VIEWER_ROUTES else editor_only
    return guard(_nav_item(route, label, icon))


def _capacity_item(role: ObjectVar) -> rx.Component:
    return mn.group(
        mn.box(
            w=8,
            h=8,
            style={
                "borderRadius": "50%",
                "backgroundColor": role.color,
                "flexShrink": "0",
            },
        ),
        mn.text(role.role_name, fz="11px", flex="1", miw=0, truncate="end"),
        de_number(
            value=role.free_days,
            suffix=" PT",
            decimal_scale=1,
            fixed_decimal_scale=True,
            style={
                "fontSize": "11px",
                "fontWeight": "500",
                "color": theme.SIDEBAR_MUTED,
                **theme.NUMERIC,
            },
        ),
        gap=8,
        wrap="nowrap",
        h=30,
        px=10,
    )


def _capacity_section() -> rx.Component:
    data = RoleCapacityState.data.to(FreeCapacityKpi)
    return _section(
        "Freie Kapazität",
        rx.cond(
            RoleCapacityState.error_message != "",
            mn.text(RoleCapacityState.error_message, fz="11px", c=theme.NEGATIVE),
            rx.cond(
                data.rows.length() > 0,
                rx.foreach(data.rows, _capacity_item),
                rx.cond(
                    RoleCapacityState.is_loading
                    | (RoleCapacityState.last_loaded == ""),
                    mn.text(
                        "Kapazität wird geladen ...",
                        fz="11px",
                        c=theme.SIDEBAR_MUTED,
                        px=10,
                    ),
                    mn.text(
                        "Keine Rollen verfügbar.",
                        fz="11px",
                        c=theme.SIDEBAR_MUTED,
                        px=10,
                    ),
                ),
            ),
        ),
    )


def _admin_section() -> rx.Component:
    """Administration needs the admin switch; project managers do not see it."""
    return requires_admin(
        _section("Administration", *(_nav_item(*item) for item in ADMIN_ITEMS))
    )


def _user_button() -> rx.Component:
    """Avatar, name and email of the signed-in user; opens the user menu."""
    return mn.group(
        mn.avatar(src=_USER.avatar_url, name=_USER.name, radius="xl", size=28),
        mn.stack(
            mn.text(_USER.name, fz="12.5px", fw=500, truncate="end"),
            mn.text(_USER.email, fz="11px", c=theme.SIDEBAR_MUTED, truncate="end"),
            gap=0,
            miw=0,
            flex="1",
        ),
        rx.icon("chevrons-up-down", size=14, color=theme.SIDEBAR_MUTED),
        gap=9,
        wrap="nowrap",
        p="6px",
        class_name="aq-nav-item",
        style={"borderRadius": "8px", "cursor": "default"},
        custom_attrs={"role": "button", "aria-label": "Benutzermenü"},
    )


def _color_mode_item(label: str, icon: str, mode: LiteralColorMode) -> rx.Component:
    """Appearance choice with a check mark on the active one."""
    return mn.menu.item(
        label,
        left_section=rx.icon(icon, size=14),
        right_section=rx.cond(
            rx.color_mode == mode, rx.icon("check", size=14), rx.fragment()
        ),
        on_click=set_color_mode(mode),
    )


def _user_menu() -> rx.Component:
    return mn.menu(
        mn.menu.target(_user_button()),
        mn.menu.dropdown(
            mn.menu.item(
                "Profil",
                left_section=rx.icon("user", size=14),
                on_click=[LoadingState.set_is_loading(True), rx.redirect("/profile")],
            ),
            mn.menu.divider(),
            mn.menu.label("Darstellung"),
            _color_mode_item("Dunkel", "moon", "dark"),
            _color_mode_item("Hell", "sun", "light"),
            _color_mode_item("System", "monitor", "system"),
            mn.menu.divider(),
            mn.menu.item(
                "Abmelden",
                left_section=rx.icon("log-out", size=14),
                on_click=SIGN_OUT,
            ),
        ),
        position="top-start",
        width="target",
    )


def sidebar() -> rx.Component:
    """The app sidebar; shared by every page."""
    return mn.box(
        editor_only(mn.box(display="none", on_mount=SidebarState.load)),
        editor_only(mn.box(display="none", on_mount=RoleCapacityState.load)),
        _window_row(),
        _brand(),
        mn.box(
            viewer_only(
                _section(
                    "Planung", *(_guarded_nav_item(*item) for item in PLANNING_ITEMS)
                )
            ),
            editor_only(_capacity_section()),
            _admin_section(),
            custom_attrs={"role": "navigation", "aria-label": "Navigation"},
            style={
                "display": "flex",
                "flexDirection": "column",
                "gap": "14px",
                "flex": "1",
                "minHeight": "0",
                "overflowY": "auto",
            },
        ),
        mn.box(
            _user_menu(),
            pt=8,
            style={"borderTop": f"0.5px solid {theme.SIDEBAR_LINE}"},
        ),
        class_name="aq-sidebar",
    )
