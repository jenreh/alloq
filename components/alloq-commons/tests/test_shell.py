"""Tests for the app shell and the window toolbar."""

import os
from unittest.mock import patch

import reflex as rx
from alloq_commons.components import shell, toolbar
from alloq_commons.components.splash import CSS as SPLASH_CSS
from alloq_commons.components.splash import SplashState, splash
from alloq_commons.desktop import DESKTOP_ENV, is_desktop


class TestWindowToolbar:
    def test_active_icon_button_uses_accent_colors(self) -> None:
        assert (
            ".aq-icon-btn[data-active=true]{"
            "background:var(--aq-accent-soft);color:var(--aq-accent);}"
        ) in shell.SHELL_CSS

    def test_renders_title_subtitle_and_actions(self) -> None:
        rendered = str(
            toolbar.window_toolbar(
                "Projekte",
                "Alle Projekte",
                center=rx.text("mitte"),
                actions=[rx.text("aktion")],
            )
        )
        for text in ("Projekte", "Alle Projekte", "mitte", "aktion"):
            assert text in rendered
        assert "data-tauri-drag-region" in rendered
        assert "aq-toolbar" in rendered

    def test_subtitle_is_optional(self) -> None:
        rendered = str(toolbar.window_toolbar("Profil"))
        assert "Profil" in rendered

    def test_reveal_button_toggles_sidebar(self) -> None:
        rendered = str(toolbar.sidebar_reveal_button())
        assert "aqToggleSidebar" in rendered
        assert "aq-sidebar-reveal" in rendered
        assert "LucidePanelLeftOpen" in rendered

    def test_controls_render(self) -> None:
        value = rx.Var.create("a")
        assert "aq-segmented" in str(
            toolbar.segmented(value, rx.console_log, ["a", "b"])
        )
        assert "Suchen" in str(toolbar.toolbar_search(value, rx.console_log))
        assert "Neu" in str(toolbar.primary_button("Neu", "plus", rx.console_log("x")))
        assert "aq-scopebar" in str(toolbar.scope_bar(rx.text("x")))


class TestAppLayout:
    def test_window_has_sidebar_pane_and_body(self) -> None:
        rendered = str(
            shell.app_layout(
                rx.text("leiste"),
                toolbar.window_toolbar("Titel"),
                rx.text("inhalt"),
                scope=rx.text("filter"),
            )
        )
        for text in ("leiste", "Titel", "inhalt", "filter", "aq-pane", "aq-window"):
            assert text in rendered
        assert "data-padded" in rendered

    def test_flush_body_for_full_pane_views(self) -> None:
        rendered = str(shell.app_layout(rx.text("s"), None, rx.text("c"), padded=False))
        assert "data-flush" in rendered


class TestSidebarScript:
    def test_restores_and_persists_collapsed_state(self) -> None:
        assert shell.STORAGE_KEY in shell.SIDEBAR_SCRIPT
        assert "sessionStorage.getItem" in shell.SIDEBAR_SCRIPT
        assert "sessionStorage.setItem" in shell.SIDEBAR_SCRIPT
        assert "localStorage" not in shell.SIDEBAR_SCRIPT
        assert shell.COLLAPSED_ATTR in shell.SIDEBAR_SCRIPT

    def test_binds_control_command_s_and_command_backslash(self) -> None:
        assert "e.metaKey&&e.ctrlKey&&k==='s'" in shell.SIDEBAR_SCRIPT
        assert "k==='\\\\'" in shell.SIDEBAR_SCRIPT

    def test_narrow_window_uses_drawer(self) -> None:
        assert f"max-width: {shell.NARROW_PX - 1}px" in shell.SIDEBAR_SCRIPT
        assert shell.OPEN_ATTR in shell.SHELL_CSS

    def test_native_window_leaves_room_for_traffic_lights(self) -> None:
        assert (
            "html[data-native][data-sidebar-collapsed] .aq-toolbar" in shell.SHELL_CSS
        )


class TestAppPage:
    def test_registers_route_with_template(self) -> None:
        from reflex_base.registry import RegistrationContext  # noqa: PLC0415

        @shell.app_page(
            route="/test/shell",
            title="Shell",
            sidebar=rx.text("leiste"),
            toolbar=toolbar.window_toolbar("Shell"),
            on_load=[rx.console_log("x")],
        )
        def _page() -> rx.Component:
            return rx.text("inhalt")

        routes = [
            kwargs.get("route")
            for _, kwargs in RegistrationContext.ensure_context().decorated_pages
        ]
        assert "/test/shell" in routes


class TestDesktop:
    def test_web_pages_keep_their_handlers(self) -> None:
        handler = rx.console_log("x")
        with patch.object(shell, "is_desktop", return_value=False):
            assert shell.desktop_handlers([handler]) == [handler]
            assert shell.desktop_handlers(handler) == [handler]
            assert shell.desktop_handlers(None) is None

    def test_desktop_pages_end_by_hiding_the_splash(self) -> None:
        handler = rx.console_log("x")
        with patch.object(shell, "is_desktop", return_value=True):
            assert shell.desktop_handlers([handler]) == [handler, SplashState.finish]
            assert shell.desktop_handlers(handler) == [handler, SplashState.finish]
            assert shell.desktop_handlers(None) == [SplashState.finish]

    def test_splash_hides_connection_warnings(self) -> None:
        rendered = str(splash())
        assert "aq-splash" in rendered
        assert "progressbar" in rendered
        assert "data-sonner-toaster" in SPLASH_CSS

    def test_splash_state(self) -> None:
        state = SplashState()
        state.finish()
        assert state.ready is True

    def test_is_desktop(self) -> None:
        with patch.dict(os.environ, {DESKTOP_ENV: "1"}):
            assert is_desktop()
        with patch.dict(os.environ, {}, clear=True):
            assert not is_desktop()
