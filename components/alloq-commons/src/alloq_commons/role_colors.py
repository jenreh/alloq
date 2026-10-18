"""Stable badge color per role, derived from its name.

The Python and JS variants use the same hash so server-built and client-side
(Var based) badges agree.
"""

import reflex as rx
from reflex.vars import Var

DEFAULT_ROLE_COLOR = "hsl(0, 0%, 88%)"
# Role badges are always pastel, so the label stays dark in both color schemes.
ROLE_BADGE_TEXT_COLOR = "#25231d"
# Avatars without a key role.
AVATAR_FALLBACK_COLOR = "#8E8E93"
_GOLDEN_ANGLE = 137.508
_GOLDEN_ANGLE_MILLI = 137508


def _hash(key: str) -> int:
    value = 5381
    for ch in key:
        value = (value * 33 + ord(ch)) & 0xFFFFFFFF
    return value


def role_color(label: str) -> str:
    """Return a pastel HSL color that is deterministic for the given role label."""
    key = (label or "").strip().lower()
    if not key:
        return DEFAULT_ROLE_COLOR
    hue = round((_hash(key) * _GOLDEN_ANGLE) % 360)
    return f"hsl({hue}, 70%, 82%)"


def role_color_var(label: Var) -> Var[str]:
    """Client-side twin of :func:`role_color` for reactive vars."""
    return rx.Var(
        f"((s) => {{ s = (s || '').trim().toLowerCase(); if (!s) return "
        f"'{DEFAULT_ROLE_COLOR}'; let h = 5381; for (const c of s) "
        f"h = (Math.imul(h, 33) + c.charCodeAt(0)) >>> 0; "
        f"return `hsl(${{Math.round((h * {_GOLDEN_ANGLE}) % 360)}}, 70%, 82%)`; "
        f"}})({label})"
    ).to(str)


def role_avatar_color(role_id: int | None) -> str:
    """Return the solid avatar fill for an employee's key role.

    Hues step by the golden angle per role id, so each role gets its own,
    well separated color. The fill is dark enough for white initials.
    """
    if not role_id:
        return AVATAR_FALLBACK_COLOR
    hue = (role_id * _GOLDEN_ANGLE_MILLI // 1000) % 360
    return f"hsl({hue}, 55%, 42%)"
