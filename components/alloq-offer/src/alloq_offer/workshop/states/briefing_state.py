"""State of the briefing tab."""

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.workshop.services.briefing import load_briefing, set_confirmed
from alloq_offer.workshop.states.helpers import current_user_name, open_offer_id
from appkit_commons.database.session import get_asyncdb_session

logger = logging.getLogger(__name__)

LOAD_ERROR = "Das Briefing konnte nicht geladen werden."
NOT_FOUND = "Diese Aussage gibt es nicht mehr."
SAVE_ERROR = "Die Änderung konnte nicht gespeichert werden."


class BriefingState(rx.State):
    """Statements of the open offer, grouped by type."""

    groups: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)

    @rx.var
    def is_empty(self) -> bool:
        return not self.groups

    async def _reload(self, offer_id: int) -> None:
        async with get_asyncdb_session() as session:
            self.groups = await load_briefing(session, offer_id)

    @rx.event
    @requires_offer_editor
    async def load_briefing(self) -> AsyncGenerator[Any]:
        offer_id = await open_offer_id(self)
        if not offer_id:
            return
        try:
            await self._reload(offer_id)
        except Exception:
            logger.exception("Loading the briefing of offer %s failed", offer_id)
            yield rx.toast.error(LOAD_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def confirm(self, statement_id: int, confirmed: bool) -> AsyncGenerator[Any]:
        """Confirm a statement as a professional decision, or withdraw it."""
        offer_id = await open_offer_id(self)
        if not offer_id:
            return
        try:
            found = await set_confirmed(
                get_asyncdb_session,
                offer_id,
                statement_id,
                confirmed=confirmed,
                user=await current_user_name(self),
                now=datetime.now(UTC),
            )
            await self._reload(offer_id)
            if not found:
                yield rx.toast.error(NOT_FOUND, position="top-right")
        except Exception:
            logger.exception("Confirming statement %s failed", statement_id)
            yield rx.toast.error(SAVE_ERROR, position="top-right")
