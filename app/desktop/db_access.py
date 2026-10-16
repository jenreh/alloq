"""Database access of alloq users, granted from the desktop app.

The desktop app connects with the signed-in person's own Entra ID token. When
that person holds `<database>_app` with ADMIN OPTION, they can give other alloq
users access. Creating a missing Entra principal also requires Entra admin rights.
The user's Entra ID
principal is created if needed and gets the role `<database>_app` that the
migration `ee66ff77aa88` created. The user then logs in with their own token.
"""

import logging
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Final

from sqlalchemy import make_url, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from appkit_commons.database.configuration import DatabaseConfig
from appkit_commons.database.session import get_asyncdb_session
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)

MAINTENANCE_DATABASE: Final = "postgres"
"""Entra ID principals can only be created in this database."""

NOT_ADMIN = (
    "Dir fehlen die Admin-Rechte in der Datenbank. Nur eine Datenbank-"
    "Administratorin oder ein Datenbank-Administrator kann Zugriff vergeben."
)
NO_PRINCIPAL = (
    "Für {email} ließ sich kein Datenbank-Benutzer anlegen. Die E-Mail-Adresse "
    "muss der Microsoft-Anmeldung (UPN) entsprechen."
)

_ROLE = text("SELECT current_database() || '_app'")
_CAN_MANAGE = text(
    "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :role) "
    "THEN pg_has_role(current_user, :role, 'MEMBER WITH ADMIN OPTION') "
    "ELSE false END"
)
_MEMBERS = text(
    "SELECT m.rolname FROM pg_auth_members am "
    "JOIN pg_roles r ON r.oid = am.roleid "
    "JOIN pg_roles m ON m.oid = am.member "
    "WHERE r.rolname = :role"
)
_PRINCIPAL = text(
    "SELECT rolname FROM pg_roles WHERE lower(rolname) = lower(:name) "
    "ORDER BY rolname = :name DESC LIMIT 1"
)
_CREATE_PRINCIPAL = text(
    "SELECT * FROM pgaadauth_create_principal(:name, false, false)"
)

type SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
type ConnectionFactory = Callable[[], AbstractAsyncContextManager[AsyncConnection]]


class DatabaseAccessError(Exception):
    """Granting or revoking failed; the message is shown to the user."""


@dataclass(frozen=True)
class AccessOverview:
    can_manage: bool
    """The signed-in database login may grant and revoke the role."""
    members: frozenset[str]
    """Lower-cased names of the logins that hold the role directly."""


def quote_identifier(name: str) -> str:
    """A Postgres identifier in double quotes, safe for any role name."""
    if "\x00" in name:
        msg = "Role names cannot contain NUL"
        raise ValueError(msg)
    return '"' + name.replace('"', '""') + '"'


@asynccontextmanager
async def maintenance_connection() -> AsyncGenerator[AsyncConnection]:
    """A short connection to the `postgres` database with the same login.

    The desktop app's connect hook fills in user and token for every engine.
    """
    config = service_registry().get(DatabaseConfig)
    url = make_url(config.url).set(database=MAINTENANCE_DATABASE)
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            yield connection
    finally:
        await engine.dispose()


async def _role(db: AsyncSession) -> str:
    return str((await db.execute(_ROLE)).scalar_one())


async def _can_manage(db: AsyncSession, role: str) -> bool:
    return bool((await db.execute(_CAN_MANAGE, {"role": role})).scalar_one())


async def _principal(db: AsyncSession, email: str) -> str | None:
    """The existing login of this email; an exact match wins over case."""
    result = await db.execute(_PRINCIPAL, {"name": email})
    return result.scalar_one_or_none()


class DatabaseAccess:
    """Grant and revoke the desktop role with the signed-in admin's rights."""

    def __init__(
        self,
        sessions: SessionFactory = get_asyncdb_session,
        maintenance: ConnectionFactory = maintenance_connection,
    ) -> None:
        self._sessions = sessions
        self._maintenance = maintenance

    async def overview(self) -> AccessOverview:
        async with self._sessions() as db:
            role = await _role(db)
            can_manage = await _can_manage(db, role)
            rows = (await db.execute(_MEMBERS, {"role": role})).scalars().all()
        return AccessOverview(
            can_manage=can_manage,
            members=frozenset(name.lower() for name in rows),
        )

    async def grant(self, email: str) -> None:
        async with self._sessions() as db:
            role = await self._managed_role(db)
            principal = await _principal(db, email)
        if principal is None:
            principal = await self._create_principal(email)
        async with self._sessions() as db:
            await db.execute(
                text(f"GRANT {quote_identifier(role)} TO {quote_identifier(principal)}")
            )
        logger.info("Granted database access to a user")

    async def revoke(self, email: str) -> None:
        async with self._sessions() as db:
            role = await self._managed_role(db)
            principal = await _principal(db, email)
            if principal is None:
                return
            await db.execute(
                text(
                    f"REVOKE {quote_identifier(role)} "
                    f"FROM {quote_identifier(principal)}"
                )
            )
        logger.info("Revoked database access of a user")

    async def _managed_role(self, db: AsyncSession) -> str:
        role = await _role(db)
        if not await _can_manage(db, role):
            raise DatabaseAccessError(NOT_ADMIN)
        return role

    async def _create_principal(self, email: str) -> str:
        """Create the Entra ID principal; only an Entra admin may do that."""
        try:
            async with self._maintenance() as connection:
                await connection.execute(_CREATE_PRINCIPAL, {"name": email})
        except DBAPIError as exc:
            logger.warning(
                "Creating the Entra ID principal failed: %s", type(exc.orig).__name__
            )
            raise DatabaseAccessError(NO_PRINCIPAL.format(email=email)) from exc
        return email
