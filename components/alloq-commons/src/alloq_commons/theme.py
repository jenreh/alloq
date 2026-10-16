"""Design tokens and the Mantine theme: the macOS look, light and dark.

All colors live here. Components use the CSS variables (`token("border")`,
`TEXT`, ...) or the Mantine palette `blue`. `TOKENS` holds the light values,
`DARK_TOKENS` the dark ones; the system appearance picks them. The desktop
window draws the sidebar with native vibrancy; the browser shows
`window-background` instead (see `GLOBAL_CSS`).

The old `--alloq-*` variables stay as aliases (`LEGACY_ALIASES`) until every
component uses the tokens directly.
"""

import appkit_mantine as mn

# Restrained blue, light → dark. Shade 6 is the accent, shade 5 the dark mode
# accent.
BLUE = [
    "#EBF2FD",
    "#D6E4FA",
    "#ADC8F3",
    "#84ABEC",
    "#6496E6",
    "#4A82E0",
    "#2E6BD6",
    "#2559B5",
    "#1D4790",
    "#15346B",
]
# Muted status palettes; Mantine fills with shade 6.
GREEN = [
    "#EAF5EE",
    "#D3EBDB",
    "#A8D5B7",
    "#7BBE92",
    "#55AA73",
    "#3D9A5E",
    "#2E8A50",
    "#22733D",
    "#195A2F",
    "#104021",
]
RED = [
    "#FCEDEB",
    "#F8D8D4",
    "#EFAFA7",
    "#E5857A",
    "#DC6457",
    "#D04E40",
    "#C04234",
    "#A6392D",
    "#842D24",
    "#61211A",
]
YELLOW = [
    "#FDF6E6",
    "#FBEBC5",
    "#F6D78E",
    "#F0C257",
    "#EBB02E",
    "#E3A115",
    "#C98C0A",
    "#A87307",
    "#875800",
    "#5F3E00",
]
ORANGE = [
    "#FDF0E8",
    "#FADDCB",
    "#F3BA97",
    "#EC9662",
    "#E67A3B",
    "#E16A24",
    "#C95A18",
    "#A84A13",
    "#873B0F",
    "#612A0A",
]
MANTINE_DARK = [
    "#E5E5EA",
    "#C7C7CC",
    "#98989D",
    "#6E6E73",
    "#48484A",
    "#3A3A3C",
    "#2C2C2E",
    "#232325",
    "#1C1C1E",
    "#121214",
]
"""Neutral macOS grays for Mantine's dark scheme (7 = body = `surface`)."""

SPLASH_COLORS = ("#5AC8FA", BLUE[6], "#8E7CC3")
"""Light blue, accent blue and lavender: the three glows of the splash."""

WINDOW_BACKGROUND = (
    "radial-gradient(900px 600px at 0% 0%, #ECEBF3 0%, transparent 60%), "
    "radial-gradient(800px 700px at 100% 100%, #E5E9F1 0%, transparent 60%), "
    "#EBEBEF"
)
"""Browser stand-in for the native sidebar material."""
WINDOW_BACKGROUND_DARK = (
    "radial-gradient(900px 600px at 0% 0%, #26252E 0%, transparent 60%), "
    "radial-gradient(800px 700px at 100% 100%, #212732 0%, transparent 60%), "
    "#1E1E22"
)
SPLASH_BACKGROUND = (
    f"radial-gradient(88% 98% at 5% 0%, {SPLASH_COLORS[0]}55 0%, transparent 78%), "
    f"radial-gradient(78% 88% at 95% 5%, {SPLASH_COLORS[1]}33 0%, transparent 78%), "
    f"radial-gradient(92% 98% at 80% 100%, {SPLASH_COLORS[2]}44 0%, "
    "transparent 78%), #F5F6FA"
)
SPLASH_BACKGROUND_DARK = (
    f"radial-gradient(88% 98% at 5% 0%, {SPLASH_COLORS[0]}30 0%, transparent 78%), "
    f"radial-gradient(78% 88% at 95% 5%, {SPLASH_COLORS[1]}2E 0%, transparent 78%), "
    f"radial-gradient(92% 98% at 80% 100%, {SPLASH_COLORS[2]}30 0%, "
    "transparent 78%), #16171B"
)

TOKENS: dict[str, str] = {
    "background": "#FBFBFC",
    "surface": "#FFFFFF",
    "surface-muted": "#F6F6F8",
    "hover": "#F3F3F6",
    "border": "#ECECF0",
    "border-strong": "#DCDCE2",
    "separator": "#F2F2F5",
    "text": "#1D1D1F",
    "text-muted": "#6B6B72",
    "text-tertiary": "#9A9AA1",
    "accent": BLUE[6],
    "accent-hover": BLUE[7],
    "accent-soft": "rgba(46, 107, 214, 0.1)",
    "sidebar-text": "#1D1D1F",
    "sidebar-muted": "rgba(29, 29, 31, 0.52)",
    "sidebar-selected": "rgba(0, 0, 0, 0.075)",
    "sidebar-hover": "rgba(0, 0, 0, 0.035)",
    "sidebar-control": "rgba(255, 255, 255, 0.55)",
    "sidebar-line": "rgba(0, 0, 0, 0.08)",
    "segmented": "#EFEFF2",
    "tag": "#F0F0F3",
    "tag-text": "#55555C",
    "meter-track": "#ECECF0",
    "positive": "#22733D",
    "positive-soft": "#E8F4EC",
    "negative": "#B4372B",
    "negative-soft": "#FBEAE7",
    "warning": "#875800",
    "warning-soft": "#FDF1D9",
    "info": "#3A5BA0",
    "info-soft": "#E9EEF9",
    "now": "#FFF8E3",
    "risk-low": "#F2F4F7",
    "risk-medium": "#FDF3D6",
    "risk-high": "#FBE4B4",
    "risk-very-high": "#F8D0A6",
    "risk-critical": "#F3BDB5",
    "window-background": WINDOW_BACKGROUND,
    "pane-shadow": (
        "0 0 0 0.5px rgba(0, 0, 0, 0.09), 0 2px 6px rgba(0, 0, 0, 0.04), "
        "0 14px 36px rgba(0, 0, 0, 0.09)"
    ),
    "card-shadow": "0 0 0 1px #ECECF0, 0 1px 2px rgba(0, 0, 0, 0.03)",
    "control-shadow": (
        "0 0 0 0.5px rgba(0, 0, 0, 0.14), 0 1px 1.5px rgba(0, 0, 0, 0.06)"
    ),
    "splash-background": SPLASH_BACKGROUND,
    "splash-track": "rgba(0, 0, 0, 0.08)",
}

DARK_TOKENS: dict[str, str] = {
    "background": "#1C1C1E",
    "surface": "#232325",
    "surface-muted": "#29292C",
    "hover": "#2C2C2F",
    "border": "#38383B",
    "border-strong": "#4A4A4E",
    "separator": "#303033",
    "text": "#F5F5F7",
    "text-muted": "#A1A1A6",
    "text-tertiary": "#7C7C82",
    "accent": BLUE[5],
    "accent-hover": BLUE[4],
    "accent-soft": "rgba(74, 130, 224, 0.2)",
    "sidebar-text": "rgba(255, 255, 255, 0.88)",
    "sidebar-muted": "rgba(235, 235, 245, 0.5)",
    "sidebar-selected": "rgba(255, 255, 255, 0.1)",
    "sidebar-hover": "rgba(255, 255, 255, 0.05)",
    "sidebar-control": "rgba(255, 255, 255, 0.08)",
    "sidebar-line": "rgba(255, 255, 255, 0.08)",
    "segmented": "#2C2C2F",
    "tag": "#333336",
    "tag-text": "#C7C7CC",
    "meter-track": "#38383B",
    "positive": "#5BC27A",
    "positive-soft": "rgba(91, 194, 122, 0.16)",
    "negative": "#FF7A6B",
    "negative-soft": "rgba(255, 122, 107, 0.16)",
    "warning": "#E3AE52",
    "warning-soft": "rgba(227, 174, 82, 0.16)",
    "info": "#8EABE8",
    "info-soft": "rgba(142, 171, 232, 0.16)",
    "now": "rgba(255, 214, 102, 0.08)",
    "risk-low": "rgba(200, 210, 220, 0.1)",
    "risk-medium": "rgba(250, 220, 120, 0.2)",
    "risk-high": "rgba(250, 200, 110, 0.35)",
    "risk-very-high": "rgba(245, 170, 100, 0.45)",
    "risk-critical": "rgba(240, 120, 105, 0.55)",
    "window-background": WINDOW_BACKGROUND_DARK,
    "pane-shadow": (
        "0 0 0 0.5px rgba(255, 255, 255, 0.1), 0 2px 6px rgba(0, 0, 0, 0.3), "
        "0 14px 36px rgba(0, 0, 0, 0.45)"
    ),
    "card-shadow": "0 0 0 1px #38383B, 0 1px 2px rgba(0, 0, 0, 0.2)",
    "control-shadow": (
        "0 0 0 0.5px rgba(255, 255, 255, 0.14), 0 1px 1.5px rgba(0, 0, 0, 0.3)"
    ),
    "splash-background": SPLASH_BACKGROUND_DARK,
    "splash-track": "rgba(255, 255, 255, 0.12)",
}
"""macOS dark appearance: elevated surfaces get lighter, accents brighter."""

LEGACY_ALIASES: dict[str, str] = {
    "bg": "background",
    "bg-base": "background",
    "surface": "surface",
    "surface-solid": "surface",
    "surface-muted": "surface-muted",
    "surface-hover": "hover",
    "accent": "accent",
    "accent-strong": "accent-hover",
    "accent-soft": "accent-soft",
    "accent-text": "accent",
    "text": "text",
    "text-muted": "text-muted",
    "border": "border",
    "border-strong": "border-strong",
    "nav-bg": "sidebar-control",
    "nav-panel-bg": "sidebar-control",
    "nav-active-bg": "sidebar-selected",
    "nav-hover-bg": "sidebar-hover",
    "nav-active-text": "sidebar-text",
    "shadow-soft": "card-shadow",
    "meter-track": "meter-track",
    "fade-bg": "surface",
    "fade-bg-hover": "hover",
    "tag-bg": "tag",
    "item-bg": "surface",
    "item-text": "text-muted",
    "risk-low": "risk-low",
    "risk-medium": "risk-medium",
    "risk-high": "risk-high",
    "risk-very-high": "risk-very-high",
    "risk-critical": "risk-critical",
}
"""Old `--alloq-*` variable → token, for components not yet migrated."""


def token(name: str) -> str:
    """CSS variable reference for a token, e.g. ``var(--aq-border)``."""
    if name not in TOKENS:
        raise KeyError(name)
    return f"var(--aq-{name})"


BACKGROUND = token("background")
SURFACE = token("surface")
SURFACE_MUTED = token("surface-muted")
HOVER = token("hover")
BORDER = token("border")
SEPARATOR = token("separator")
TEXT = token("text")
TEXT_MUTED = token("text-muted")
TEXT_TERTIARY = token("text-tertiary")
ACCENT = token("accent")
ACCENT_SOFT = token("accent-soft")
SIDEBAR_TEXT = token("sidebar-text")
SIDEBAR_MUTED = token("sidebar-muted")
SIDEBAR_SELECTED = token("sidebar-selected")
SIDEBAR_HOVER = token("sidebar-hover")
SIDEBAR_LINE = token("sidebar-line")
POSITIVE = token("positive")
NEGATIVE = token("negative")
WARNING = token("warning")
PANE_SHADOW = token("pane-shadow")
CARD_SHADOW = token("card-shadow")

FONT_FAMILY = (
    "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'SF Pro Display', "
    "'Helvetica Neue', 'Segoe UI', Roboto, Arial, sans-serif"
)
FONT_MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"
RADIUS = "14px"
SHADOW = "0 1px 2px rgba(0, 0, 0, 0.03)"

CARD = {
    "backgroundColor": SURFACE,
    "borderRadius": "12px",
    "boxShadow": CARD_SHADOW,
}
"""White card on the content pane."""

NUMERIC = {"fontVariantNumeric": "tabular-nums", "whiteSpace": "nowrap"}
"""Style for numbers: tabular digits."""


NATIVE_ATTR = "data-native"
"""Set on <html> inside the desktop window (see `NATIVE_SCRIPT`)."""

NATIVE_SCRIPT = (
    "if (window.__TAURI__ || window.__TAURI_INTERNALS__) "
    f"document.documentElement.setAttribute('{NATIVE_ATTR}', '');"
)

HEAD_SCRIPTS = (NATIVE_SCRIPT,)


def _variables(tokens: dict[str, str]) -> str:
    return "".join(f"--aq-{name}:{value};" for name, value in tokens.items())


def _aliases() -> str:
    return "".join(
        f"--alloq-{alias}:var(--aq-{target});"
        for alias, target in LEGACY_ALIASES.items()
    )


GLOBAL_CSS = (
    f":root{{color-scheme:light dark;{_variables(TOKENS)}{_aliases()}}}"
    + f".dark{{{_variables(DARK_TOKENS)}}}"
    + f"html,body{{background:{token('window-background')};color:{TEXT};"
    + f"font-family:{FONT_FAMILY};-webkit-font-smoothing:antialiased;"
    + "letter-spacing:-0.005em;overscroll-behavior:none;}"
    # Radix paints its root; the window material must show through.
    + ".radix-themes{background:transparent !important;"
    + f"--default-font-family:{FONT_FAMILY};}}"
    # The desktop window is transparent: native vibrancy replaces the page
    # background.
    + f"html[{NATIVE_ATTR}],html[{NATIVE_ATTR}] body"
    + "{background:transparent !important;}"
    # Desktop apps don't select UI text on click; inputs and cells still do.
    + "nav,header,button{-webkit-user-select:none;user-select:none;}"
)

MANTINE_THEME = mn.create_theme(
    primary_color="blue",
    primary_shade={"light": 6, "dark": 5},
    colors={
        "blue": BLUE,
        "green": GREEN,
        "red": RED,
        "yellow": YELLOW,
        "orange": ORANGE,
        "dark": MANTINE_DARK,
    },
    font_family=FONT_FAMILY,
    font_family_monospace=FONT_MONO,
    headings={"fontFamily": FONT_FAMILY, "fontWeight": "650"},
    font_sizes={
        "xs": "11.5px",
        "sm": "13px",
        "md": "14px",
        "lg": "16px",
        "xl": "18px",
    },
    default_radius="md",
    radius={"xs": "5px", "sm": "6px", "md": "7px", "lg": "12px", "xl": RADIUS},
    shadows={"xs": SHADOW, "sm": SHADOW, "md": PANE_SHADOW},
    cursor_type="default",
    components={
        "Button": {"styles": {"root": {"fontWeight": 500}}},
        "Modal": {
            "defaultProps": {"radius": "lg", "centered": True},
            "styles": {"title": {"fontWeight": 650, "fontSize": "15px"}},
        },
        "Drawer": {"styles": {"title": {"fontWeight": 650, "fontSize": "15px"}}},
        "Paper": {"defaultProps": {"radius": "lg"}},
        "Badge": {
            "styles": {
                "root": {"textTransform": "none", "fontWeight": 500, "flexShrink": 0},
                "label": {"overflow": "visible"},
            }
        },
        "SegmentedControl": {"defaultProps": {"radius": "md"}},
        "Menu": {"defaultProps": {"radius": "md"}},
        "Tooltip": {"defaultProps": {"radius": "sm"}},
    },
)
