"""State of the offer workshop page."""

import logging
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.repository import offer_repo
from alloq_offer.workshop.routes import WORKSHOP_ROUTE_SUFFIX
from alloq_offer.workshop.services.workspace import open_workspace
from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.states import LoginState

logger = logging.getLogger(__name__)

TAB_DRAFT = "draft"
TAB_MAP = "map"
TAB_CHAPTERS = "chapters"
TAB_BRIEFING = "briefing"
TAB_EXPORT = "export"
TABS: list[dict[str, str]] = [
    {"value": TAB_DRAFT, "label": "Entwurf"},
    {"value": TAB_MAP, "label": "Story Map"},
    {"value": TAB_CHAPTERS, "label": "Kapitel"},
    {"value": TAB_BRIEFING, "label": "Briefing"},
    {"value": TAB_EXPORT, "label": "Export"},
]
NOT_FOUND = "Angebot nicht gefunden."
LOAD_ERROR = "Die Werkstatt konnte nicht geladen werden."
SAVE_ERROR = "Die Einstellung konnte nicht gespeichert werden."


class WorkshopState(rx.State):
    """Workspace of one offer and the active tab."""

    offer_id: rx.Field[int] = rx.field(0)
    offer_title: rx.Field[str] = rx.field("")
    offer_customer: rx.Field[str] = rx.field("")
    template_label: rx.Field[str] = rx.field("")
    doc_state: rx.Field[str] = rx.field("")
    auto_draft: rx.Field[bool] = rx.field(False)
    active_tab: rx.Field[str] = rx.field(TAB_DRAFT)
    loaded: rx.Field[bool] = rx.field(False)
    not_found: rx.Field[bool] = rx.field(False)

    @rx.var
    def subtitle(self) -> str:
        if not self.loaded:
            return ""
        return (
            f"{self.offer_customer} · Vorlage {self.template_label} · {self.doc_state}"
        )

    def _route_offer_id(self) -> int:
        path = self.router.url.path
        if not path.endswith(WORKSHOP_ROUTE_SUFFIX):
            return 0
        segment = path.removesuffix(WORKSHOP_ROUTE_SUFFIX).rsplit("/", 1)[-1]
        try:
            return int(segment)
        except ValueError:
            return 0

    @rx.event
    def set_tab(self, tab: str) -> None:
        self.active_tab = tab

    @rx.event
    @requires_offer_editor
    async def load_workshop(self) -> AsyncGenerator[Any]:
        """Load the offer and create its workspace on first visit."""
        self.loaded = False
        self.not_found = False
        offer_id = self._route_offer_id()
        try:
            async with get_asyncdb_session() as session:
                offer = await offer_repo.find_by_id(session, offer_id)
                if offer is None:
                    self.not_found = True
                    return
                login = await self.get_state(LoginState)
                user = await login.authenticated_user
                workspace = await open_workspace(
                    session, offer_id, user.name if user else ""
                )
                self.offer_id = offer.id
                self.offer_title = offer.title
                self.offer_customer = offer.customer
                self.template_label = workspace.template_key.replace("_", " ").upper()
                self.doc_state = workspace.doc_state
                self.auto_draft = workspace.auto_draft
                self.loaded = True
        except Exception:
            logger.exception("Loading workshop of offer %s failed", offer_id)
            yield rx.toast.error(LOAD_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def set_auto_draft(self, value: bool) -> AsyncGenerator[Any]:
        """Store whether new usable sources start a draft automatically."""
        if not self.loaded:
            return
        try:
            async with get_asyncdb_session() as session:
                workspace = await open_workspace(session, self.offer_id, "")
                workspace.auto_draft = value
            self.auto_draft = value
        except Exception:
            logger.exception("Saving auto draft of offer %s failed", self.offer_id)
            yield rx.toast.error(SAVE_ERROR, position="top-right")
