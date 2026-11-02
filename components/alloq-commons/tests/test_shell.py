"""Tests for the app shell and the window toolbar."""

from pathlib import Path

import reflex as rx
from alloq_commons.components import shell, toolbar

ASSETS_CSS = Path(__file__).parents[3] / "assets" / "css"


def _css(name: str) -> str:
    return (ASSETS_CSS / name).read_text()


class TestWindowToolbar:
    def test_active_icon_button_uses_accent_colors(self) -> None:
        css = _css("aq-shell.css")
        assert ".aq-icon-btn[data-active=true] {" in css
        assert "background: var(--aq-accent-soft);" in css
        assert "color: var(--aq-accent);" in css

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
        assert shell.OPEN_ATTR in _css("aq-shell.css")
        assert f"max-width: {shell.NARROW_PX - 1}px" in _css("aq-shell.css")


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
