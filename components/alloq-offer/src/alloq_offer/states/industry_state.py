"""State of the industries administration page."""

import logging
from collections.abc import AsyncGenerator
from typing import Any, Final

import reflex as rx
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from alloq_offer.entities import IndustryEntity
from alloq_offer.models import Industry, IndustryCreate
from alloq_offer.repository import industry_repo
from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.decorators import requires_admin

logger = logging.getLogger(__name__)

DUPLICATE_MESSAGE: Final = "Diese Branche gibt es bereits."
HINT_NAME: Final = "Bitte einen Namen mit höchstens 100 Zeichen angeben."
NOT_FOUND: Final = "Branche nicht gefunden."


def in_use_message(count: int) -> str:
    """Why an industry that offers still use cannot be deleted."""
    offers = "einem Angebot" if count == 1 else f"{count} Angeboten"
    return f"Die Branche wird noch in {offers} verwendet und bleibt erhalten."


async def load_industries() -> list[Industry]:
    """All industries ordered by name."""
    async with get_asyncdb_session() as session:
        entities = await industry_repo.find_all_ordered(session)
        return [Industry(**e.to_dict()) for e in entities]


class IndustryState(rx.State):
    """Admins add, rename and delete the industries offers can use."""

    industries: rx.Field[list[Industry]] = rx.field(default_factory=list)
    selected_industry: rx.Field[Industry | None] = rx.field(None)
    is_loading: rx.Field[bool] = rx.field(False)
    add_modal_open: rx.Field[bool] = rx.field(False)
    edit_modal_open: rx.Field[bool] = rx.field(False)
    search_filter: rx.Field[str] = rx.field("")

    @rx.event
    def set_search_filter(self, value: str) -> None:
        self.search_filter = value

    @rx.var
    def filtered_industries(self) -> list[Industry]:
        needle = self.search_filter.strip().casefold()
        return [i for i in self.industries if needle in i.name.casefold()]

    @rx.event
    def open_add_modal(self) -> None:
        self.add_modal_open = True

    @rx.event
    def close_add_modal(self) -> None:
        self.add_modal_open = False

    @rx.event
    def open_edit_modal(self, industry_id: int) -> None:
        self.selected_industry = next(
            (i for i in self.industries if i.id == industry_id), None
        )
        self.edit_modal_open = self.selected_industry is not None

    @rx.event
    def close_edit_modal(self) -> None:
        self.edit_modal_open = False
        self.selected_industry = None

    @rx.event
    @requires_admin
    async def load_industries(self) -> AsyncGenerator[Any]:
        """Load all industries; the loading row only shows on the first load."""
        if not self.industries:
            self.is_loading = True
            yield
        try:
            self.industries = await load_industries()
        except Exception:
            logger.exception("Failed to load industries")
            yield rx.toast.error(
                "Die Branchen konnten nicht geladen werden.", position="top-right"
            )
        finally:
            self.is_loading = False

    @rx.event
    @requires_admin
    async def create_industry(self, form_data: dict) -> AsyncGenerator[Any]:
        try:
            data = IndustryCreate(name=form_data.get("name", ""))
            async with get_asyncdb_session() as session:
                await industry_repo.create(session, IndustryEntity(name=data.name))
        except ValidationError:
            yield rx.toast.error(HINT_NAME, position="top-right")
            return
        except IntegrityError:
            yield rx.toast.error(DUPLICATE_MESSAGE, position="top-right")
            return
        except Exception:
            logger.exception("Failed to create industry")
            yield rx.toast.error(
                "Fehler beim Anlegen der Branche.", position="top-right"
            )
            return
        self.industries = await load_industries()
        self.add_modal_open = False
        yield rx.toast.info(f"Branche '{data.name}' angelegt.", position="top-right")

    @rx.event
    @requires_admin
    async def update_industry(self, form_data: dict) -> AsyncGenerator[Any]:
        """Rename the selected industry; offers show the new name."""
        if not self.selected_industry:
            yield rx.toast.error(NOT_FOUND, position="top-right")
            return
        try:
            data = IndustryCreate(name=form_data.get("name", ""))
            async with get_asyncdb_session() as session:
                entity = await industry_repo.find_by_id(
                    session, self.selected_industry.id
                )
                if entity:
                    entity.name = data.name
                    await industry_repo.update(session, entity)
        except ValidationError:
            yield rx.toast.error(HINT_NAME, position="top-right")
            return
        except IntegrityError:
            yield rx.toast.error(DUPLICATE_MESSAGE, position="top-right")
            return
        except Exception:
            logger.exception("Failed to update industry")
            yield rx.toast.error(
                "Fehler beim Speichern der Branche.", position="top-right"
            )
            return
        if not entity:
            yield rx.toast.error(NOT_FOUND, position="top-right")
            return
        self.industries = await load_industries()
        self.close_edit_modal()
        yield rx.toast.info(f"Branche '{data.name}' gespeichert.", position="top-right")

    @rx.event
    @requires_admin
    async def delete_industry(self, industry_id: int) -> AsyncGenerator[Any]:
        """Delete an industry that no offer uses."""
        try:
            async with get_asyncdb_session() as session:
                used = await industry_repo.count_offers(session, industry_id)
                deleted = not used and await industry_repo.delete_by_id(
                    session, industry_id
                )
        except Exception:
            logger.exception("Failed to delete industry %d", industry_id)
            yield rx.toast.error(
                "Fehler beim Löschen der Branche.", position="top-right"
            )
            return
        if used:
            yield rx.toast.error(in_use_message(used), position="top-right")
            return
        if not deleted:
            yield rx.toast.error(NOT_FOUND, position="top-right")
            return
        self.industries = await load_industries()
        yield rx.toast.info("Branche gelöscht.", position="top-right")
