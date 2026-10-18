"""Planning toolbar settings kept in the browser's localStorage.

The page reads and writes the key itself. `rx.LocalStorage` vars are not used,
because a login or a denied hydrate resets the backend state, and the next
delta would write the defaults back into the browser.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass

STORAGE_KEY = "alloq_planning_view"
READ_SCRIPT = (
    f"(() => {{ try {{ return window.localStorage.getItem('{STORAGE_KEY}') || ''; }}"
    " catch (e) { return ''; } })()"
)


@dataclass(frozen=True)
class ViewSettings:
    """State of the planning toolbar toggles."""

    compact: bool = False
    collapsed: bool = False
    project_scope: bool = False
    employee_scope: bool = False


_FIELDS = tuple(field.name for field in dataclasses.fields(ViewSettings))


def parse_view_settings(raw: object) -> ViewSettings:
    """Settings from the stored JSON; anything unreadable counts as off."""
    if not isinstance(raw, str) or not raw:
        return ViewSettings()
    try:
        data = json.loads(raw)
    except ValueError:
        return ViewSettings()
    if not isinstance(data, dict):
        return ViewSettings()
    return ViewSettings(**{name: data.get(name) is True for name in _FIELDS})


def view_settings_script(settings: ViewSettings) -> str:
    """JavaScript that stores the settings in the browser."""
    value = json.dumps(json.dumps(dataclasses.asdict(settings)))
    return (
        f"try {{ window.localStorage.setItem('{STORAGE_KEY}', {value}); }}"
        " catch (e) {}"
    )
