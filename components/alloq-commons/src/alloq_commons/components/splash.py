"""Full-window splash with the app icon; fades out once the app is ready.

Only the desktop app shows it: the embedded backend needs a few seconds to
start, and the prebuilt frontend is on screen before that. While it shows,
Reflex's connection warnings ("Cannot connect to server" toast and the
wifi-off pulser) are hidden; they fire until the backend is up.
"""

from typing import Any

import reflex as rx

import appkit_mantine as mn
from alloq_commons import theme
from alloq_commons.components.toolbar import DRAG

FADE_MS = 450
ICON_PX = 88
Z_INDEX = 2147483647


class SplashState(rx.State):
    """Stays ready for the whole session, so page changes show no splash.

    `finish` is the last on_load event of every page. A client's events run
    one after another, so it fires once the backend is up and the page data
    is in.
    """

    ready: bool = False

    @rx.event
    def finish(self) -> None:
        self.ready = True


def _progress_bar() -> rx.Component:
    """Thin indeterminate bar, like a macOS launch progress."""
    return mn.box(
        mn.box(
            style={
                "width": "40%",
                "height": "100%",
                "borderRadius": "2px",
                "backgroundColor": theme.ACCENT,
                "animation": "aq-splash-bar 1.1s ease-in-out infinite",
            }
        ),
        custom_attrs={"role": "progressbar", "aria-label": "Wird geladen"},
        style={
            "width": "120px",
            "height": "3px",
            "overflow": "hidden",
            "borderRadius": "2px",
            "backgroundColor": theme.token("splash-track"),
        },
    )


def splash() -> rx.Component:
    hidden = SplashState.ready
    attrs: dict[str, Any] = {**DRAG, "aria-hidden": rx.cond(hidden, "true", "false")}
    return mn.box(
        rx.image(
            src=rx.asset("img/alloq_icon.svg"),
            alt="",
            width=f"{ICON_PX}px",
            height=f"{ICON_PX}px",
            draggable=False,
            style={
                "padding": "16px",
                "borderRadius": "20px",
                "background": "#FFFFFF",
                "boxShadow": (
                    "0 0 0 0.5px rgba(0,0,0,0.08), 0 10px 24px rgba(0,40,110,0.16)"
                ),
            },
            custom_attrs=DRAG,
        ),
        mn.text(
            "alloq", fz="20px", fw=650, lts="-0.015em", c=theme.TEXT, custom_attrs=DRAG
        ),
        _progress_bar(),
        class_name="aq-splash",
        custom_attrs=attrs,
        style={
            "position": "fixed",
            "inset": "0",
            "zIndex": Z_INDEX,
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "center",
            "gap": "14px",
            "background": theme.token("splash-background"),
            "opacity": rx.cond(hidden, "0", "1"),
            "visibility": rx.cond(hidden, "hidden", "visible"),
            "pointerEvents": rx.cond(hidden, "none", "auto"),
            # Visibility flips only after the fade, so the fade stays visible.
            "transition": rx.cond(
                hidden,
                f"opacity {FADE_MS}ms ease, visibility 0s linear {FADE_MS}ms",
                "none",
            ),
        },
    )
