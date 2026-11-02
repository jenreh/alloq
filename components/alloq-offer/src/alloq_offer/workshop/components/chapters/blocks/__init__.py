"""One module per chapter type: its read-only view and its editing view."""

from typing import Any

from reflex.vars import ObjectVar

Row = ObjectVar[dict[str, Any]]
