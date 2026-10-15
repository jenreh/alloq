"""Database access switch on the users page of the desktop app."""

import logging
from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Any

import reflex as rx
from alloq_commons.desktop import is_desktop

from appkit_user.authentication.decorators import requires_admin

from app.desktop.db_access import AccessOverview, DatabaseAccess, DatabaseAccessError

logger = logging.getLogger(__name__)

FAILED = "Der Datenbankzugriff ließ sich nicht ändern. Bitte versuche es erneut."


@lru_cache(maxsize=1)
def get_access() -> DatabaseAccess:
    return DatabaseAccess()


class DatabaseAccessState(rx.State):
    can_manage: rx.Field[bool] = rx.field(False)
    """The signed-in database login may grant access (a database admin)."""
    members: rx.Field[list[str]] = rx.field(default_factory=list)
    """Lower-cased emails of the users with access."""
    pending_email: rx.Field[str] = rx.field("")

    @rx.var
    def locked(self) -> bool:
        """The switch shows the access but cannot change it."""
        return not self.can_manage

    def _apply(self, overview: AccessOverview) -> None:
        self.can_manage = overview.can_manage
        self.members = sorted(overview.members)

    @rx.event
    @requires_admin
    async def load(self) -> AsyncGenerator[Any]:
        """Only the desktop app connects as the person; the server cannot grant."""
        if not is_desktop():
            return
        try:
            self._apply(await get_access().overview())
        except Exception:
            logger.exception("Loading the database access failed")
            self.can_manage = False
            self.members = []
        yield

    @rx.event
    @requires_admin
    async def toggle(self, email: str) -> AsyncGenerator[Any]:
        if not email or not self.can_manage or self.pending_email:
            return
        revoke = email.lower() in self.members
        self.pending_email = email
        yield
        try:
            access = get_access()
            if revoke:
                await access.revoke(email)
            else:
                await access.grant(email)
            self._apply(await access.overview())
            message = "entzogen" if revoke else "vergeben"
            yield rx.toast.success(
                f"Datenbankzugriff für {email} {message}.", position="top-right"
            )
        except DatabaseAccessError as exc:
            yield rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Changing the database access failed")
            yield rx.toast.error(FAILED, position="top-right")
        finally:
            self.pending_email = ""
