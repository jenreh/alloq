"""Whether the app runs as the Tauri desktop app.

`ALLOQ_DESKTOP=1` marks desktop builds and the desktop dev task; the embedded
runtime is recognized by the app root the Tauri host sets. Components use this
at compile time, so a desktop build gets the desktop variants (login, splash).
"""

import os
from typing import Final

DESKTOP_ENV: Final = "ALLOQ_DESKTOP"
DESKTOP_ROOT_ENV: Final = "REFLEX_DESKTOP_APP_ROOT"


def is_desktop() -> bool:
    return os.environ.get(DESKTOP_ENV) == "1" or DESKTOP_ROOT_ENV in os.environ
