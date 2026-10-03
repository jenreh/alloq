"""Tests for app.components.navbar_collapsible module."""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

import reflex as rx

from app.components.navbar_collapsible import (
    _ALL_SECTIONS,
    _SECTIONS_WITH_ITEMS,
    NavbarCollapseState,
    _gated,
    _is_route_active,
    _logo,
    app_navbar_collapsible,
)

# ============================================================================
# State Tests
# ============================================================================


class TestNavbarCollapseState:
    """Tests for the NavbarCollapseState Reflex state class."""

    def test_initial_collapsed_value(self) -> None:
        state = NavbarCollapseState()
        assert state.collapsed == "1"

    def test_is_collapsed_false_when_zero(self) -> None:
        state = NavbarCollapseState()
        state.collapsed = "0"
        assert state.is_collapsed is False

    def test_is_collapsed_true_when_one(self) -> None:
        state = NavbarCollapseState()
        state.collapsed = "1"
        assert state.is_collapsed is True

    def test_active_title_returns_matching_section_label(self) -> None:
        state = NavbarCollapseState()
        state.active_section_id = _SECTIONS_WITH_ITEMS[0]["id"]
        assert state.active_title == _SECTIONS_WITH_ITEMS[0]["label"]

    def test_active_title_returns_default_when_not_found(self) -> None:
        state = NavbarCollapseState()
        state.active_section_id = "nonexistent_section"
        assert state.active_title == _SECTIONS_WITH_ITEMS[0]["label"]

    def test_toggle_from_expanded_to_collapsed(self) -> None:
        state = NavbarCollapseState()
        state.collapsed = "0"
        state.toggle()
        assert state.collapsed == "1"

    def test_toggle_from_collapsed_to_expanded(self) -> None:
        state = NavbarCollapseState()
        state.collapsed = "1"
        state.toggle()
        assert state.collapsed == "0"

    def test_collapse_sets_collapsed(self) -> None:
        state = NavbarCollapseState()
        state.collapsed = "0"
        state.collapse()
        assert state.collapsed == "1"

    def test_collapse_no_op_when_already_collapsed(self) -> None:
        state = NavbarCollapseState()
        state.collapsed = "1"
        state.collapse()
        assert state.collapsed == "1"

    def test_select_section_same_section_toggles_panel(self) -> None:
        state = NavbarCollapseState()
        section_id = _SECTIONS_WITH_ITEMS[0]["id"]
        state.active_section_id = section_id
        state.collapsed = "0"
        # Calling with same section should toggle (close)
        gen = state.select_section(section_id)
        # Exhaust the generator
        results = list(gen)
        assert state.collapsed == "1"
        # No redirect when collapsed
        assert len(results) == 0

    def test_select_section_same_section_opens_when_collapsed(self) -> None:
        state = NavbarCollapseState()
        section_id = _SECTIONS_WITH_ITEMS[0]["id"]
        state.active_section_id = section_id
        state.collapsed = "1"
        # Calling with same section when collapsed should open
        gen = state.select_section(section_id)
        results = list(gen)
        assert state.collapsed == "0"
        # Should yield a redirect since panel opened
        assert len(results) == 1

    def test_select_section_different_section_opens_panel(self) -> None:
        state = NavbarCollapseState()
        state.active_section_id = "some_other_id"
        state.collapsed = "1"
        section_id = _SECTIONS_WITH_ITEMS[0]["id"]
        gen = state.select_section(section_id)
        results = list(gen)
        assert state.active_section_id == section_id
        assert state.collapsed == "0"
        # Should yield a redirect
        assert len(results) == 1

    def test_reopen_same_section_stays_on_current_item(self) -> None:
        state = NavbarCollapseState()
        section = _SECTIONS_WITH_ITEMS[0]
        state.active_section_id = section["id"]
        state.collapsed = "1"

        with patch.object(
            NavbarCollapseState,
            "_current_path",
            return_value=section["items"][-1]["url"],
        ):
            results = list(state.select_section(section["id"]))

        assert state.collapsed == "0"
        assert results == []


def test_section_ids_are_unique() -> None:
    ids = [section["id"] for section in _ALL_SECTIONS]

    assert len(ids) == len(set(ids))


# ============================================================================
# Helper Tests
# ============================================================================


class TestGated:
    """Tests for the _gated helper function."""

    def test_no_guards_returns_component_unchanged(self) -> None:
        component = rx.text("test")
        entry: dict = {"label": "Test"}
        result = _gated(entry, component)
        assert result is component

    def test_requires_admin_wraps_component(self) -> None:
        component = rx.text("test")
        entry: dict = {"label": "Test", "requires_admin": True}
        result = _gated(entry, component)
        # Result should be different (wrapped)
        assert result is not component

    def test_requires_role_wraps_component(self) -> None:
        component = rx.text("test")
        entry: dict = {"label": "Test", "requires_role": "admin"}
        result = _gated(entry, component)
        assert result is not component

    def test_both_guards_wraps_component(self) -> None:
        component = rx.text("test")
        entry: dict = {
            "label": "Test",
            "requires_admin": True,
            "requires_role": "editor",
        }
        result = _gated(entry, component)
        assert result is not component


class TestIsRouteActive:
    """Tests for the _is_route_active helper."""

    def test_returns_rx_var_for_index(self) -> None:
        result = _is_route_active("/")
        # Should return a Reflex conditional (not a plain bool)
        assert result is not None

    def test_returns_rx_var_for_non_index(self) -> None:
        result = _is_route_active("/projects")
        assert result is not None


class TestAppNavbarCollapsible:
    """Tests for the public component factory."""

    def test_returns_component(self) -> None:
        result = app_navbar_collapsible()
        assert isinstance(result, rx.Component)


class TestStaticAssetsUnderFrontendPath:
    """Static asset URLs must carry Reflex's frontend_path when one is set."""

    @staticmethod
    def _render_with_frontend_path(
        prefix: str, factory: Callable[[], rx.Component] = app_navbar_collapsible
    ) -> str:
        config = MagicMock()
        config.prepend_frontend_path.side_effect = lambda path: f"{prefix}{path}"
        with patch("reflex.assets.get_config", return_value=config):
            return str(factory())

    def test_logo_is_prefixed(self) -> None:
        rendered = self._render_with_frontend_path("/alloq", _logo)

        assert "/alloq/img/logo.svg" in rendered

    def test_section_icons_are_prefixed(self) -> None:
        rendered = self._render_with_frontend_path("/alloq")

        assert "/alloq/icons/project_icon.svg" in rendered
        assert "/alloq/icons/project_icon_dark.svg" in rendered

    def test_no_unprefixed_asset_paths(self) -> None:
        rendered = self._render_with_frontend_path("/alloq")

        for raw in ('"/img/', '"/icons/', "`/img/", "`/icons/"):
            assert raw not in rendered
