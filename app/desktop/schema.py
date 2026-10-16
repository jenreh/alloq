"""Database schema check of the desktop app.

Migrations run only on the server. A desktop app that does not match the
database schema must not write to it, so sign-in stops with a clear message
instead.
"""

from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

KNOWN_REVISIONS: Final = (
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
