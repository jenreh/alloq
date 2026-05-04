"""Two-column collapsible sidebar navbar with section-based sub-menus.

Layout:

    ┌────┬──────────────────────┐
    │ ☰  │ <Section title>   ⟨  │
    │ 🏠 │  🏠  Item 1          │
    │ 📁 │  📁  Item 2          │
    │ 👥 │       …              │
    │ ⚙  │                      │
    │ ❓ │                      │
    │ </>│                      │
    │ 👤 │                      │
    └────┴──────────────────────┘

* The narrow rail (always visible) lists one icon per *section*.
* Clicking a rail icon switches the panel to that section's sub-menu and
  opens it; clicking the same icon again closes the panel.
* The user avatar at the bottom of the rail opens a hover-card with a
  small profile/logout sub-menu (no duplicate user card in the panel).
* The active section and panel collapsed state are persisted to
  localStorage.
"""

import logging
from collections.abc import Generator
from typing import Any, Final

import reflex as rx

import appkit_mantine as mn
from appkit_commons.registry import service_registry
from appkit_ui.global_states import LoadingState
from appkit_user.authentication.components.components import (
    requires_admin,
    requires_role,
)
from appkit_user.authentication.states import LoginState

from app.configuration import AppConfig

logger = logging.getLogger(__name__)

_config = service_registry().get(AppConfig)
VERSION: Final[str] = (
    f"{_config.version}-{_config.environment}"
    if _config.environment
    else _config.version
)

RAIL_WIDTH: Final[str] = "64px"
_TOOLTIP_OFFSET: Final[int] = 18  # flush against the rail's right edge
PANEL_WIDTH: Final[str] = "240px"
MOBILE_BREAKPOINT: Final[str] = "sm"

_TEXT_COLOR = "var(--alloq-text)"
_DIM_COLOR = "var(--alloq-text-muted)"
_ACTIVE_BG = "var(--alloq-nav-active-bg)"
_ACTIVE_TEXT = "var(--alloq-nav-active-text)"
_HOVER_BG = "var(--alloq-nav-hover-bg)"
_RAIL_BG = "var(--alloq-nav-bg)"
_PANEL_BG = "var(--alloq-nav-panel-bg)"
_BORDER = "1px solid var(--alloq-border)"


# --------------------------------------------------------------------------- #
# Example section data — each section has its own sub-menu.
# --------------------------------------------------------------------------- #


SECTIONS: Final[list[dict[str, Any]]] = [
    {
        "id": "dashboard",
        "label": "Dashboard",
        "icon": "house",
        "url": "/",
    },
    {
        "id": "projects",
        "label": "Ressourcenplanung",
        "icon": "briefcase-business",
        "url": "/plan",
    },
    {
        "id": "projects",
        "label": "Projekte",
        "icon": "folder-open",
        "url": "/projects",
    },
    {
        "id": "team",
        "label": "Team",
        "icon": "users",
        "url": "/team",
    },
]


FOOTER_SECTIONS: Final[list[dict[str, Any]]] = [
    {
        "id": "settings",
        "label": "Administration",
        "icon": "settings",
        "requires_admin": True,
        "items": [
            {
                "label": "Benutzer",
                "icon": "users",
                "url": "/admin/users",
            },
            {
                "label": "Rollen",
                "icon": "shield",
                "url": "/admin/roles",
            },
        ],
    },
]


_ALL_SECTIONS: Final[list[dict[str, Any]]] = SECTIONS + FOOTER_SECTIONS
_SECTIONS_WITH_ITEMS: Final[list[dict[str, Any]]] = [
    s for s in _ALL_SECTIONS if s.get("items")
]
_DEFAULT_SECTION_ID: Final[str] = (
    _SECTIONS_WITH_ITEMS[0]["id"] if _SECTIONS_WITH_ITEMS else SECTIONS[0]["id"]
)
_SECTION_FIRST_URL: Final[dict[str, str]] = {
    s["id"]: s["items"][0]["url"] for s in _ALL_SECTIONS if s.get("items")
}


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #


class NavbarCollapseState(rx.State):
    """Persisted panel state: open/closed + active section."""

    collapsed: str = rx.LocalStorage("0", name="navbar_collapse_state")
    active_section_id: str = rx.LocalStorage(
        _DEFAULT_SECTION_ID, name="navbar_active_section"
    )

    @rx.var
    def is_collapsed(self) -> bool:
        return self.collapsed == "1"

    @rx.var
    def active_title(self) -> str:
        for section in _SECTIONS_WITH_ITEMS:
            if section["id"] == self.active_section_id:
                return section["label"]
        return _SECTIONS_WITH_ITEMS[0]["label"] if _SECTIONS_WITH_ITEMS else ""

    @rx.event
    def toggle(self) -> None:
        new_value = "0" if self.collapsed == "1" else "1"
        logger.debug("Toggling navbar panel to: %s", new_value)
        self.collapsed = new_value

    @rx.event
    def collapse(self) -> None:
        """Force the panel into the collapsed state."""
        if self.collapsed != "1":
            logger.debug("Collapsing navbar panel")
            self.collapsed = "1"

    @rx.event
    def select_section(self, section_id: str) -> Generator[Any, Any, None]:
        """Select a section. If it's already active, toggle the panel.

        When the panel opens, automatically navigates to the first sub-item.
        """
        if section_id == self.active_section_id:
            self.collapsed = "0" if self.collapsed == "1" else "1"
        else:
            self.active_section_id = section_id
            self.collapsed = "0"
        logger.debug("Selected section %s (collapsed=%s)", section_id, self.collapsed)
        if self.collapsed == "0" and section_id in _SECTION_FIRST_URL:
            yield rx.redirect(_SECTION_FIRST_URL[section_id])


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _is_route_active(url: str) -> Any:
    current = rx.State.router.page.path
    target = url.lower()
    # Reflex serves the index page at both "/" and "/index"; treat them as
    # equivalent so the dashboard icon highlights on either path.
    if target in ("/", "/index"):
        return (current == "/") | (current == "/index")
    return current == target


def _gated(entry: dict[str, Any], component: rx.Component) -> rx.Component:
    """Wrap `component` with role/admin guards declared on `entry`.

    Recognised keys: ``requires_admin: bool``, ``requires_role: str``.
    Stacks both guards if both are set.
    """
    result = component
    if role := entry.get("requires_role"):
        result = requires_role(result, role=role)
    if entry.get("requires_admin"):
        result = requires_admin(result)
    return result


def _rail_section_button(section: dict[str, Any]) -> rx.Component:
    """Icon button representing a section in the rail.

    - Section with `items`: clicking switches the panel to that section's
      sub-menu (or toggles the panel if already active).
    - Section with `url` (no items): clicking navigates directly.
    """
    section_id = section["id"]
    icon_name = section["icon"]
    label = section["label"]

    if section.get("items"):
        child_active: Any = None
        for item in section["items"]:
            if child_url := item.get("url"):
                match = _is_route_active(child_url)
                child_active = match if child_active is None else child_active | match
        panel_open = (~NavbarCollapseState.is_collapsed) & (
            NavbarCollapseState.active_section_id == section_id
        )
        route_active_when_closed = (
            NavbarCollapseState.is_collapsed
            if child_active is None
            else NavbarCollapseState.is_collapsed & child_active
        )
        is_active_section = panel_open | route_active_when_closed
        target = mn.box(
            mn.center(
                rx.icon(icon_name, size=20),
                w="40px",
                h="40px",
                on_click=NavbarCollapseState.select_section(section_id),
                style={
                    "cursor": "pointer",
                    "border_radius": "var(--radius-2)",
                    "background_color": rx.cond(
                        is_active_section, _ACTIVE_BG, "transparent"
                    ),
                    "color": rx.cond(is_active_section, _ACTIVE_TEXT, _TEXT_COLOR),
                    "transition": "background-color 0.2s ease",
                    "_hover": {"background_color": _HOVER_BG},
                },
            ),
            style={"display": "flex"},
        )
    else:
        url = section["url"]
        # URL-only icons highlight only when the panel is closed AND the route
        # matches; while a panel is open the open section owns the highlight.
        active = NavbarCollapseState.is_collapsed & _is_route_active(url)
        target = mn.box(
            rx.link(
                mn.center(
                    rx.icon(icon_name, size=20),
                    w="40px",
                    h="40px",
                    style={
                        "border_radius": "var(--radius-2)",
                        "background_color": rx.cond(active, _ACTIVE_BG, "transparent"),
                        "color": rx.cond(active, _ACTIVE_TEXT, _TEXT_COLOR),
                        "transition": "background-color 0.2s ease",
                        "_hover": {"background_color": _HOVER_BG},
                    },
                ),
                href=url,
                underline="none",
                on_click=[
                    LoadingState.set_is_loading(True),
                    NavbarCollapseState.collapse(),
                ],
            ),
            style={"display": "flex"},
        )

    return mn.tooltip(target, label=label, position="right", offset=_TOOLTIP_OFFSET)


def _panel_nav_item(label: str, icon: str, url: str) -> rx.Component:
    """Icon + label link inside the expanded detail panel."""
    active = _is_route_active(url)
    return rx.link(
        mn.group(
            rx.icon(icon, size=18, style={"flex_shrink": "0"}),
            mn.text(
                label,
                size="sm",
                style={
                    "white_space": "nowrap",
                    "overflow": "hidden",
                    "text_overflow": "ellipsis",
                },
            ),
            gap="sm",
            wrap="nowrap",
            align="center",
            w="100%",
            p="0.5em",
            style={
                "border_radius": "var(--radius-2)",
                "background_color": rx.cond(active, _ACTIVE_BG, "transparent"),
                "color": rx.cond(active, _ACTIVE_TEXT, _TEXT_COLOR),
                "transition": "background-color 0.2s ease",
                "_hover": {"background_color": _HOVER_BG},
            },
        ),
        href=url,
        underline="none",
        on_click=LoadingState.set_is_loading(True),
        width="100%",
    )


def _panel_section_items(section: dict[str, Any]) -> rx.Component:
    """Render a section's items inside the panel."""
    return mn.stack(
        *[
            _gated(
                item,
                _panel_nav_item(
                    **{
                        k: v
                        for k, v in item.items()
                        if k not in ("requires_admin", "requires_role")
                    }
                ),
            )
            for item in section["items"]
        ],
        gap="2px",
        w="100%",
        p="sm",
    )


# --------------------------------------------------------------------------- #
# User avatar (direct link to profile, no sub-menu)
# --------------------------------------------------------------------------- #


def _user_avatar() -> rx.Component:
    avatar_component = mn.center(
        mn.avatar(
            src=LoginState.user.avatar_url,
            name=LoginState.user.name,
            radius="xl",
            size="md",
            ml="3px",
            mb="6px",
            color="var(--alloq-accent-strong)",
        ),
        w="100%",
        p="xs",
        style={"cursor": "pointer", "flex_shrink": "0"},
    )

    # When panel is expanded, show simple tooltip with link to profile
    expanded_view = mn.tooltip(
        mn.box(
            rx.link(
                avatar_component,
                href="/profile",
                underline="none",
                on_click=LoadingState.set_is_loading(True),
            ),
            style={"display": "flex"},
        ),
        label=LoginState.user.name,
        position="right",
        offset=7,
    )

    # When panel is collapsed, show dropdown menu with profile/logout on click
    collapsed_view = mn.menu(
        mn.menu.target(
            mn.box(
                avatar_component,
                style={"display": "flex", "cursor": "pointer"},
            ),
        ),
        mn.menu.dropdown(
            mn.menu.item(
                mn.group(
                    rx.icon("user", size=14),
                    mn.text("Profil", size="sm"),
                    gap="xs",
                    align="center",
                ),
                on_click=[
                    LoadingState.set_is_loading(True),
                    rx.redirect("/profile"),
                ],
            ),
            mn.menu.divider(),
            mn.menu.item(
                mn.group(
                    rx.icon("log-out", size=14),
                    mn.text("Abmelden", size="sm"),
                    gap="xs",
                    align="center",
                ),
                color="red",
                on_click=[
                    LoginState.terminate_session,
                    LoginState.logout,
                ],
            ),
        ),
        trigger="hover",
        position="right-end",
        with_arrow=True,
        arrow_position="center",
        open_delay=0,
        close_delay=200,
    )

    # Show collapse view when panel is collapsed, expanded view when open
    return rx.cond(
        NavbarCollapseState.is_collapsed,
        collapsed_view,
        expanded_view,
    )


# --------------------------------------------------------------------------- #
# Rail and Panel
# --------------------------------------------------------------------------- #


def _dark_mode_toggle() -> rx.Component:
    return mn.tooltip(
        mn.box(
            mn.center(
                rx.icon(
                    rx.color_mode_cond(light="moon", dark="sun"),
                    size=20,
                ),
                w="40px",
                h="40px",
                on_click=rx.toggle_color_mode,
                style={
                    "cursor": "pointer",
                    "border_radius": "var(--radius-2)",
                    "color": _TEXT_COLOR,
                    "transition": "background-color 0.2s ease",
                    "_hover": {"background_color": _HOVER_BG},
                },
            ),
            style={"display": "flex"},
        ),
        label=rx.color_mode_cond(light="Dark Mode", dark="Light Mode"),
        position="right",
        offset=_TOOLTIP_OFFSET,
    )


def _logo() -> rx.Component:
    return mn.center(
        mn.tooltip(
            mn.image(
                src="/img/logo.svg",
                h="32px",
                w="32px",
                fit="contain",
                on_click=NavbarCollapseState.toggle,
                style={"cursor": "pointer"},
            ),
            label=rx.cond(
                NavbarCollapseState.is_collapsed,
                "Menü öffnen",
                "Menü schließen",
            ),
            position="right",
            offset=_TOOLTIP_OFFSET,
        ),
        w=RAIL_WIDTH,
        p="xs",
        style={"flex_shrink": "0"},
    )


def _rail() -> rx.Component:
    return mn.stack(
        #        mn.center(
        mn.stack(
            *[_gated(s, _rail_section_button(s)) for s in SECTIONS],
            gap="3px",
            align="center",
            #           ),
            w="100%",
            h="100%",
            mt="1rem",
        ),
        mn.stack(
            *[_gated(s, _rail_section_button(s)) for s in FOOTER_SECTIONS],
            _dark_mode_toggle(),
            gap="3px",
            align="center",
            w="100%",
            style={"flex_shrink": "0"},
        ),
        _user_avatar(),
        gap="xs",
        h="100%",
        w=RAIL_WIDTH,
        style={
            #            "border_right": _BORDER,
            "flex_shrink": "0",
            "background_color": _RAIL_BG,
        },
    )


def _panel_section_content(section: dict[str, Any]) -> rx.Component:
    """Panel content rendered when this section is the active one."""
    return _gated(
        section,
        rx.cond(
            NavbarCollapseState.active_section_id == section["id"],
            _panel_section_items(section),
            rx.fragment(),
        ),
    )


def _panel_user_card() -> rx.Component:
    """User info card at the bottom of the expanded panel."""
    return mn.group(
        mn.box(
            mn.text(
                LoginState.user.name,
                size="sm",
                fw="bold",
                c=_TEXT_COLOR,
                truncate=True,
            ),
            mn.text(
                LoginState.user.email,
                size="xs",
                c=_DIM_COLOR,
                truncate=True,
            ),
            flex="1",
            min_width="0",
            overflow="hidden",
        ),
        mn.menu(
            mn.menu.target(
                mn.action_icon(
                    rx.icon("ellipsis-vertical", size=16),
                    variant="subtle",
                    color="gray",
                    size="sm",
                    aria_label="Optionen",
                ),
            ),
            mn.menu.dropdown(
                mn.menu.item(
                    mn.group(
                        rx.icon("user", size=14),
                        mn.text("Profil", size="sm"),
                        gap="xs",
                        align="center",
                    ),
                    on_click=[
                        LoadingState.set_is_loading(True),
                        rx.redirect("/profile"),
                    ],
                ),
                mn.menu.divider(),
                mn.menu.item(
                    mn.group(
                        rx.icon("log-out", size=14),
                        mn.text("Abmelden", size="sm"),
                        gap="xs",
                        align="center",
                    ),
                    color="red",
                    on_click=[
                        LoginState.terminate_session,
                        LoginState.logout,
                    ],
                ),
            ),
            trigger="hover",
            position="top-end",
            with_arrow=True,
            arrow_position="center",
            open_delay=0,
            close_delay=200,
        ),
        wrap="nowrap",
        align="center",
        gap="sm",
        w="100%",
        p="md",
        style={
            "border_top": _BORDER,
            "flex_shrink": "0",
        },
    )


def _panel() -> rx.Component:
    return mn.stack(
        mn.group(
            mn.text(
                NavbarCollapseState.active_title,
                size="md",
                fw="bold",
                c=_TEXT_COLOR,
            ),
            mn.action_icon(
                rx.icon("panel-left-close", size=18),
                variant="subtle",
                color="gray",
                size="md",
                on_click=NavbarCollapseState.toggle,
                aria_label="Detail-Panel schließen",
            ),
            justify="space-between",
            wrap="nowrap",
            align="center",
            w="100%",
            p="md",
            style={
                "flex_shrink": "0",
                # "border_bottom": _BORDER,
            },
        ),
        rx.box(
            class_name=rx.cond(
                LoadingState.is_loading, "rainbow-gradient-bar", "default-bar"
            ),
        ),
        mn.scroll_area.stateful(
            mn.stack(
                *[_panel_section_content(s) for s in _SECTIONS_WITH_ITEMS],
                gap="0",
                w="100%",
            ),
            type="hover",
            scrollbars="y",
            scrollbar_size="6px",
            show_controls=False,
            persist_key="navbar_panel_scroll",
            flex="1",
            min_height="0",
            width="100%",
        ),
        _panel_user_card(),
        gap="0",
        h="100%",
        bg=_PANEL_BG,
        style={
            "border_left": rx.cond(NavbarCollapseState.is_collapsed, "none", _BORDER),
            "width": rx.cond(NavbarCollapseState.is_collapsed, "0px", PANEL_WIDTH),
            "overflow": "hidden",
            "transition": "width 0.3s ease",
            "flex_shrink": "0",
        },
    )


# --------------------------------------------------------------------------- #
# Public components
# --------------------------------------------------------------------------- #


def app_navbar_collapsible() -> rx.Component:
    """Two-column desktop navbar: rail + collapsible section panel."""
    return mn.stack(
        # _logo(),
        mn.group(
            mn.group(
                _rail(),
                align="stretch",
                wrap="nowrap",
                gap="0",
                bg=_RAIL_BG,
            ),
            _panel(),
            gap="0",
            wrap="nowrap",
            align="stretch",
            h="calc(100dvh - 64px)",
            style={
                "border_radius": "var(--radius-3)",
                "border": _BORDER,
                "box_shadow": "var(--alloq-shadow-soft)",
                "overflow": "hidden",
                "background_color": _RAIL_BG,
            },
        ),
        gap="md",
        visible_from=MOBILE_BREAKPOINT,
        style={
            "position": "sticky",
            "top": "2.25rem",
            "margin": "18px 18px 2rem 12px",
        },
    )
