"""Database schema check of the desktop app.

Migrations run only on the server. A desktop app that does not match the
database schema must not write to it, so sign-in stops with a clear message
instead.
"""

from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

KNOWN_REVISIONS: Final = (
    "e2f3a4b5c6d7",
    "d1e2f3a4b5c6",
    "c0d1e2f3a4b5",
    "b9c0d1e2f3a4",
    "a8b9c0d1e2f3",
    "f7a8b9c0d1e2",
    "e6f7a8b9c0d1",
    "d5e6f7a8b9c0",
    "c4d5e6f7a8b9",
    "b3c4d5e6f7a8",
    "a2b3c4d5e6f7",
    "f1a2b3c4d5e6",
    "e023b4c5d6f7",
    "df12a3b4c5e6",
    "ce01a2b3c4d5",
    "bd91ef12ac34",
    "bc90de12fa34",
    "ab89cd01ef23",
    "fa67bc89de01",
    "ef56ab78cd90",
    "de45fa67bc89",
    "cd34ef56ab78",
    "bc23de45fa67",
    "ab12cd34ef56",
    "ff77aa88bb99",
    "ee66ff77aa88",
    "dd55ee66ff77",
    "cc44dd55ee66",
    "bb33cc44dd55",
    "aa11bb22cc33",
)
"""Alembic history this app version knows, newest first (a test keeps it
current). The app expects the newest one."""
EXPECTED_REVISION: Final = KNOWN_REVISIONS[0]


async def schema_problem(session: AsyncSession) -> str | None:
    """None when the database has the expected schema, else a message."""
    result = await session.execute(text("SELECT version_num FROM alembic_version"))
    current = result.scalar_one_or_none()
    if current == EXPECTED_REVISION:
        return None
    if current in KNOWN_REVISIONS:
        return (
            f"Die Datenbank hat den älteren Stand {current}, diese App braucht "
            f"{EXPECTED_REVISION}. Die Migration auf dem Server steht noch aus."
        )
    return (
        f"Die Datenbank hat den Stand {current or 'unbekannt'}, den diese App "
        "nicht kennt. Bitte die App aktualisieren."
    )
