"""Desktop profile: active before the configuration is loaded.

Called from `app/__init__.py`, right before `configure()`, so the import order
of `rxconfig` and `app` (it differs between `reflex run`, hot reload and the
embedded runtime) does not matter.
"""

import os
from typing import Final

DESKTOP_ENV: Final = "ALLOQ_DESKTOP"  # = alloq_commons.desktop.DESKTOP_ENV
DESKTOP_ROOT_ENV: Final = "REFLEX_DESKTOP_APP_ROOT"  # set by the Tauri host
DESKTOP_PROFILE: Final = "desktop"
FAKE_PROFILE: Final = "desktop_fake"
FAKE_ENV: Final = "ALLOQ_FAKE_ENTRA_EMAIL"


def is_desktop() -> bool:
    return os.environ.get(DESKTOP_ENV) == "1" or in_bundle()


def in_bundle() -> bool:
    """Running inside the built app (embedded backend)."""
    return DESKTOP_ROOT_ENV in os.environ


def activate_desktop_profile() -> None:
    """Add the desktop profile last, so it overrides every server value."""
    if not is_desktop():
        return
    os.environ[DESKTOP_ENV] = "1"
    profiles = [p for p in os.environ.get("PROFILES", "").split(",") if p.strip()]
    wanted = [DESKTOP_PROFILE]
    if os.environ.get(FAKE_ENV) and not in_bundle():
        wanted.append(FAKE_PROFILE)  # local DB credentials, development only
    missing = [p for p in wanted if p not in profiles]
    if missing:
        os.environ["PROFILES"] = ",".join([*profiles, *missing])


def prepare_embedded_backend() -> None:
    """The bundled app serves a prebuilt frontend; its payload has no assets/.

    Backend-only mode keeps `rx.asset` from checking files that only the
    frontend build needed.
    """
    if in_bundle():
        os.environ.setdefault("REFLEX_BACKEND_ONLY", "true")
