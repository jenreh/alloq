"""Theme tokens: CSS variables, dark mode, Mantine theme, native window."""

import re

import pytest
from alloq_commons import theme


class TestTokens:
    def test_token_references_css_variable(self) -> None:
        assert theme.token("border") == "var(--aq-border)"

    def test_unknown_token_raises(self) -> None:
        with pytest.raises(KeyError):
            theme.token("teal")

    def test_global_css_defines_every_token(self) -> None:
        for name, value in theme.TOKENS.items():
            assert f"--aq-{name}:{value};" in theme.GLOBAL_CSS

    def test_dark_mode_overrides_every_token(self) -> None:
        assert set(theme.DARK_TOKENS) == set(theme.TOKENS)
        assert "@media (prefers-color-scheme: dark)" not in theme.GLOBAL_CSS
        for name, value in theme.DARK_TOKENS.items():
            assert f"--aq-{name}:{value};" in theme.GLOBAL_CSS.split(".dark{")[1]
        assert "color-scheme:light dark" in theme.GLOBAL_CSS

    def test_dark_class_overrides_tokens(self) -> None:
        """Reflex sets `.dark` on <html>; tokens must follow it too."""
        assert ".dark{" in theme.GLOBAL_CSS

    def test_accent_is_restrained_blue(self) -> None:
        assert theme.TOKENS["accent"] == "#2E6BD6"


class TestLegacyAliases:
    def test_every_alias_points_to_a_token(self) -> None:
        for alias, target in theme.LEGACY_ALIASES.items():
            assert target in theme.TOKENS, alias
            assert f"--alloq-{alias}:var(--aq-{target});" in theme.GLOBAL_CSS

    def test_aliases_cover_variables_used_in_code(self) -> None:
        used = {"text", "text-muted", "border", "surface-muted", "fade-bg"}
        assert used <= set(theme.LEGACY_ALIASES)

    def test_no_warm_colors_left(self) -> None:
        for value in (*theme.TOKENS.values(), *theme.DARK_TOKENS.values()):
            assert "f1ca45" not in value.lower()
            assert "6f9fa5" not in value.lower()


class TestMantineTheme:
    def test_primary_palette_is_blue_with_accent_at_shade_6(self) -> None:
        assert theme.MANTINE_THEME["primaryColor"] == "blue"
        assert theme.MANTINE_THEME["colors"]["blue"][6] == theme.TOKENS["accent"]
        assert len(theme.BLUE) == 10

    def test_dark_palette_is_neutral(self) -> None:
        assert theme.MANTINE_THEME["colors"]["dark"] == theme.MANTINE_DARK
        for color in theme.MANTINE_DARK:
            red, green, blue = (int(color[i : i + 2], 16) for i in (1, 3, 5))
            assert max(red, green, blue) - min(red, green, blue) <= 6

    def test_uses_system_font(self) -> None:
        assert theme.MANTINE_THEME["fontFamily"] == theme.FONT_FAMILY
        assert "-apple-system" in theme.FONT_FAMILY


class TestNativeWindow:
    def test_native_script_marks_tauri_window(self) -> None:
        assert "__TAURI__" in theme.NATIVE_SCRIPT
        assert theme.NATIVE_SCRIPT in theme.HEAD_SCRIPTS

    def test_native_window_is_transparent(self) -> None:
        assert f"html[{theme.NATIVE_ATTR}] body" in theme.GLOBAL_CSS
        assert "background:transparent !important" in theme.GLOBAL_CSS

    def test_does_not_override_saved_color_mode(self) -> None:
        assert theme.HEAD_SCRIPTS == (theme.NATIVE_SCRIPT,)


def test_global_css_is_balanced() -> None:
    assert theme.GLOBAL_CSS.count("{") == theme.GLOBAL_CSS.count("}")
    assert not re.search(r";;", theme.GLOBAL_CSS)
