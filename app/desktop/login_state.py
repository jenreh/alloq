"""Desktop sign-in: Microsoft Entra ID first, then the alloq session.

1. Use the cached Microsoft account, else sign in in the system browser.
2. Connect to Postgres with the user's token and check the schema version.
3. Find the alloq user by email and open the usual appkit session.

There is no password login in the desktop app: without a signed-in Microsoft
account it has no database access to check a password against.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Any

import reflex as rx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from appkit_commons.database.session import (
    get_async_session_manager,
    get_asyncdb_session,
    get_session_manager,
)
from appkit_user.authentication.backend.database.entities import UserEntity
from appkit_user.authentication.backend.database.user_repository import user_repo
from appkit_user.authentication.session_validation import safe_redirect_path
from appkit_user.authentication.states import LoginState

from app.configuration import configure
from app.desktop.config import DesktopConfig
from app.desktop.entra import Account, EntraSignIn, SignInError
from app.desktop.fake import FakeEntraSignIn, fake_email
from app.desktop.schema import schema_problem

logger = logging.getLogger(__name__)

NO_ACCOUNT = (
    "Für {email} gibt es kein alloq-Konto. Bitte wende dich an eine "
    "Administratorin oder einen Administrator."
)
FAILED = "Anmeldung fehlgeschlagen. Bitte versuche es erneut."
STATUS_MESSAGES = {
    "inactive": "Dein alloq-Konto ist deaktiviert.",
    "not_verified": "Dein alloq-Konto ist noch nicht freigeschaltet.",
}


@lru_cache(maxsize=1)
def get_sign_in() -> EntraSignIn | FakeEntraSignIn:
    email = fake_email()
    if email:
        return FakeEntraSignIn(email)
    return EntraSignIn(configure().app.desktop or DesktopConfig())


async def reset_connections() -> None:
    """Close pooled connections; they carry the previous user's identity."""
    await get_async_session_manager().close()
    if get_session_manager.cache_info().currsize:
        get_session_manager().close()


async def find_user(db: AsyncSession, email: str) -> UserEntity | None:
    """The alloq user with this email, ignoring case (Entra UPNs vary)."""
    statement = select(UserEntity).where(func.lower(UserEntity.email) == email.lower())
    result = await db.execute(statement)
    return result.scalars().first()


async def allowed_user(db: AsyncSession, account: Account) -> UserEntity:
    """The active alloq user of the account, on a matching schema.

    Raises:
        SignInError: Schema mismatch, unknown or inactive user.
    """
    problem = await schema_problem(db)
    if problem and fake_email():
        # Local development databases may lag behind; the fake sign-in exists
        # to test the app against them.
        logger.warning("Schema mismatch ignored: %s", problem)
    elif problem:
        raise SignInError(problem)
    user = await find_user(db, account.email)
    if user is None:
        raise SignInError(NO_ACCOUNT.format(email=account.email))
    allowed, status = user_repo.validate_user_for_login(user)
    if not allowed:
        raise SignInError(STATUS_MESSAGES.get(status, FAILED))
    return user


async def microsoft_account(sign_in: EntraSignIn | FakeEntraSignIn) -> Account:
    """Cached account if possible, else the browser sign-in."""
    account = await asyncio.to_thread(sign_in.sign_in_silently)
    if account is None:
        account = await asyncio.to_thread(sign_in.sign_in_interactively)
    return account


class DesktopLoginState(LoginState):
    """Sign-in button of the desktop login page."""

    @rx.event(background=True)
    async def sign_in_with_microsoft(self) -> AsyncGenerator[Any]:
        async with self:
            if self.is_loading:
                return
            self.is_loading = True
            self.error_message = ""
        try:
            account = await microsoft_account(get_sign_in())
            await reset_connections()
            async with get_asyncdb_session() as db:
                user = await allowed_user(db, account)
                async with self:
                    target = await self._prepare_login()
                    await self._create_session(db, user)
                    self.redirect_to = ""
            logger.info("Desktop sign-in for user %s", user.id)
            # Straight to the page the user wanted: `LoginState.redir` would
            # read the cached `is_authenticated` from before the sign-in.
            yield rx.redirect(safe_redirect_path(target) or self.homepage)
        except SignInError as exc:
            async with self:
                self.error_message = str(exc)
        except Exception:
            logger.exception("Desktop sign-in failed")
            async with self:
                self.error_message = FAILED
        finally:
            async with self:
                self.is_loading = False

    @rx.event
    async def sign_out(self) -> list[Any]:
        """End the session and forget the Microsoft account on this Mac."""
        events = await self.logout()  # type: ignore[operator]
        await asyncio.to_thread(get_sign_in().sign_out)
        await reset_connections()
        return events
