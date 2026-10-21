"""State of the offers page: list, inspector, form and persistence."""

import logging
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Final

import reflex as rx
from alloq_commons.access import requires_offer_editor
from pydantic import ValidationError

from alloq_offer.entities import OfferEntity, OfferStateEnum
from alloq_offer.models import Industry, Offer, OfferCreate
from alloq_offer.repository import industry_repo, offer_repo
from alloq_offer.services.offers import (
    FILTER_ALL,
    FILTER_ARCHIVED,
    FILTERS,
    SORT_COLUMNS,
    apply_state_change,
    group_offers,
    margin_pct,
    total_days,
    totals,
    visible_offers,
)
from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.decorators import is_authenticated

logger = logging.getLogger(__name__)

TEXT_FIELDS: Final = ("title", "customer", "key_accounter", "sharepoint_url")
NUMBER_FIELDS: Final = (
    "person_days",
    "risk_buffer_days",
    "production_cost",
    "recommended_price",
)
FORM_FIELDS: Final = (
    *TEXT_FIELDS,
    *NUMBER_FIELDS,
    "industry_id",
    "sent_date",
    "state",
)
REQUIRED_FIELDS: Final = (
    "title",
    "customer",
    "key_accounter",
    "industry_id",
    "person_days",
    "production_cost",
    "recommended_price",
)
HINT_INVALID: Final = (
    "Bitte alle Pflichtfelder ausfüllen (Zahlen nicht negativ, Link mit https://)."
)
ERROR_SAVE: Final = "Das Angebot konnte nicht gespeichert werden."
NOT_FOUND: Final = "Angebot nicht gefunden."


def _today() -> date:
    return datetime.now(tz=UTC).date()


def _empty_form() -> dict[str, str]:
    form = dict.fromkeys(FORM_FIELDS, "")
    form["risk_buffer_days"] = "0"
    form["state"] = OfferStateEnum.NEW.value
    return form


def _form_from(offer: Offer) -> dict[str, str]:
    form = _empty_form()
    for field in (*TEXT_FIELDS, "industry_id", "state"):
        form[field] = str(getattr(offer, field) or "")
    for field in NUMBER_FIELDS:
        form[field] = str(getattr(offer, field))
    form["sent_date"] = offer.sent_date.isoformat() if offer.sent_date else ""
    return form


def number_text(value: Any) -> str:
    """Normalize a number input value (float or German text) to "1234.5"."""
    if value is None:
        return ""
    text = str(value).replace("€", "").replace(" ", "").strip()
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return str(Decimal(text))
    except InvalidOperation:
        return ""


def _parse_date(value: str) -> date | None:
    return date.fromisoformat(value[:10]) if value else None


class OfferState(rx.State):
    """Offers list with inspector, create/edit form and archive actions."""

    offers: rx.Field[list[Offer]] = rx.field(default_factory=list)
    industries: rx.Field[list[Industry]] = rx.field(default_factory=list)
    is_loading: rx.Field[bool] = rx.field(False)
    search_filter: rx.Field[str] = rx.field("")
    list_filter: rx.Field[str] = rx.field(FILTER_ALL)
    sort_column: rx.Field[str] = rx.field("")
    sort_desc: rx.Field[bool] = rx.field(False)
    inspected_id: rx.Field[int] = rx.field(0)
    inspector_open: str = rx.LocalStorage("1", name="alloq_offers_inspector")

    form_open: rx.Field[bool] = rx.field(False)
    editing_id: rx.Field[int] = rx.field(0)
    form: rx.Field[dict[str, str]] = rx.field(default_factory=_empty_form)
    form_version: rx.Field[int] = rx.field(0)
    date_draft_id: rx.Field[int] = rx.field(0)
    date_draft: rx.Field[str] = rx.field("")

    # --- UI-only handlers -------------------------------------------------

    @rx.event
    def set_search_filter(self, value: str) -> None:
        self.search_filter = value

    @rx.event
    def set_list_filter(self, value: str) -> None:
        self.list_filter = value if value in FILTERS else FILTER_ALL

    @rx.event
    def reset_filters(self) -> None:
        self.search_filter = ""
        self.list_filter = FILTER_ALL

    @rx.event
    def toggle_sort(self, column: str) -> None:
        if column not in SORT_COLUMNS:
            return
        if self.sort_column == column:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_column = column
            self.sort_desc = False

    @rx.event
    def inspect(self, offer_id: int) -> None:
        self.inspected_id = offer_id

    @rx.event
    def toggle_inspector(self) -> None:
        self.inspector_open = "0" if self.inspector_open == "1" else "1"

    @rx.event
    def open_create_modal(self) -> None:
        self.editing_id = 0
        self.form = _empty_form()
        self.form_version += 1
        self.form_open = True

    @rx.event
    def open_edit_modal(self, offer_id: int) -> None:
        offer = next((o for o in self.offers if o.id == offer_id), None)
        if offer is None:
            return
        self.inspected_id = offer_id
        self.editing_id = offer_id
        self.form = _form_from(offer)
        self.form_version += 1
        self.form_open = True

    @rx.event
    def close_modal(self) -> None:
        self.form_open = False

    @rx.event
    def set_form_field(self, field: str, value: Any) -> None:
        """Keep one form value; numbers are normalized to plain decimals."""
        if field not in FORM_FIELDS:
            return
        text = number_text(value) if field in NUMBER_FIELDS else str(value or "")
        self.form = {**self.form, field: text}

    @rx.event
    def set_inspected_sent_date(self, offer_id: int, value: str) -> None:
        """Keep a typed or picked date until the input loses focus."""
        self.date_draft_id = offer_id
        self.date_draft = value or ""

    @rx.event
    def set_sent_date_today(self, offer_id: int) -> None:
        self.date_draft_id = offer_id
        self.date_draft = _today().isoformat()

    # --- Computed vars ----------------------------------------------------

    @rx.var
    def show_inspector(self) -> bool:
        return self.inspector_open == "1"

    @rx.var
    def visible(self) -> list[Offer]:
        return visible_offers(
            self.offers,
            query=self.search_filter,
            list_filter=self.list_filter,
            sort_column=self.sort_column,
            sort_desc=self.sort_desc,
        )

    @rx.var
    def grouped(self) -> dict[str, list[Offer]]:
        """Visible offers per status; empty under the archive filter."""
        if self.list_filter == FILTER_ARCHIVED:
            return {}
        return group_offers(self.visible)

    @rx.var
    def new_rows(self) -> list[Offer]:
        return self.grouped.get(OfferStateEnum.NEW.value, [])

    @rx.var
    def in_progress_rows(self) -> list[Offer]:
        return self.grouped.get(OfferStateEnum.IN_PROGRESS.value, [])

    @rx.var
    def sent_rows(self) -> list[Offer]:
        return self.grouped.get(OfferStateEnum.SENT.value, [])

    @rx.var
    def archived_rows(self) -> list[Offer]:
        return self.visible if self.list_filter == FILTER_ARCHIVED else []

    @rx.var
    def row_count(self) -> int:
        return len(self.visible)

    @rx.var
    def total_person_days(self) -> float:
        return float(totals(self.visible).person_days)

    @rx.var
    def total_production_cost(self) -> float:
        return float(totals(self.visible).production_cost)

    @rx.var
    def total_recommended_price(self) -> float:
        return float(totals(self.visible).recommended_price)

    @rx.var
    def subtitle(self) -> str:
        active = [o for o in self.offers if not o.archived]
        open_count = sum(o.state != OfferStateEnum.SENT for o in active)
        return f"{len(active)} Angebote · {open_count} offen"

    @rx.var
    def inspected(self) -> Offer | None:
        """The selected offer, if it is still visible."""
        return next((o for o in self.visible if o.id == self.inspected_id), None)

    @rx.var
    def industry_options(self) -> list[dict[str, str]]:
        return [{"value": str(i.id), "label": i.name} for i in self.industries]

    @rx.var
    def inspected_total_days(self) -> float:
        return float(total_days(self.inspected)) if self.inspected else 0.0

    @rx.var
    def inspected_margin(self) -> str:
        margin = margin_pct(self.inspected) if self.inspected else None
        if margin is None:
            return "–"
        return f"{margin:.1f}".replace(".", ",") + " %"

    @rx.var
    def inspected_sent_date(self) -> str:
        offer = self.inspected
        if offer and offer.id == self.date_draft_id:
            return self.date_draft
        return offer.sent_date.isoformat() if offer and offer.sent_date else ""

    @rx.var
    def is_form_invalid(self) -> bool:
        return any(not self.form.get(f, "").strip() for f in REQUIRED_FIELDS)

    # --- Data handlers ----------------------------------------------------

    def _named(self, entity: OfferEntity) -> Offer:
        """Read model of ``entity`` with the name of its industry."""
        names = {i.id: i.name for i in self.industries}
        offer = Offer(**entity.to_dict())
        return offer.model_copy(update={"industry": names.get(offer.industry_id, "")})

    def _replace(self, offer: Offer) -> None:
        if any(o.id == offer.id for o in self.offers):
            self.offers = [offer if o.id == offer.id else o for o in self.offers]
        else:
            self.offers = [offer, *self.offers]

    @rx.event
    @is_authenticated
    async def load_offers(self) -> AsyncGenerator[Any]:
        """Load all offers and industries; the spinner only shows on the first load."""
        if not self.offers:
            self.is_loading = True
            yield
        try:
            async with get_asyncdb_session() as session:
                industries = await industry_repo.find_all_ordered(session)
                self.industries = [Industry(**i.to_dict()) for i in industries]
                entities = await offer_repo.find_all_ordered(session)
                self.offers = [self._named(e) for e in entities]
        except Exception:
            logger.exception("Failed to load offers")
            yield rx.toast.error(
                "Die Angebote konnten nicht geladen werden.", position="top-right"
            )
        finally:
            self.is_loading = False

    def _data_from(self, form_data: dict) -> OfferCreate:
        values = {**self.form}
        for field in TEXT_FIELDS:
            if field in form_data:
                values[field] = str(form_data[field] or "")
        sent = _parse_date(values["sent_date"])
        return OfferCreate(
            **{k: v for k, v in values.items() if k != "sent_date"},
            sent_date=apply_state_change(
                OfferStateEnum.NEW, sent, values["state"], _today()
            ),
        )

    async def _save_form(self, form_data: dict, offer_id: int) -> AsyncGenerator[Any]:
        try:
            data = self._data_from(form_data)
            async with get_asyncdb_session() as session:
                if offer_id:
                    entity = await offer_repo.find_by_id(session, offer_id)
                    if entity is None:
                        yield rx.toast.error(NOT_FOUND, position="top-right")
                        return
                    for key, value in data.model_dump().items():
                        setattr(entity, key, value)
                    await session.commit()
                    await session.refresh(entity)
                else:
                    entity = await offer_repo.create(
                        session, OfferEntity(**data.model_dump())
                    )
                saved = self._named(entity)
        except ValidationError:
            yield rx.toast.error(HINT_INVALID, position="top-right")
            return
        except Exception:
            logger.exception("Failed to save offer")
            yield rx.toast.error(ERROR_SAVE, position="top-right")
            return
        self._replace(saved)
        self.inspected_id = saved.id
        self.form_open = False
        verb = "aktualisiert" if offer_id else "angelegt"
        yield rx.toast.info(f"Angebot '{saved.title}' {verb}.", position="top-right")

    @rx.event
    @requires_offer_editor
    async def create_offer(self, form_data: dict) -> AsyncGenerator[Any]:
        async for event in self._save_form(form_data, 0):
            yield event

    @rx.event
    @requires_offer_editor
    async def update_offer(self, form_data: dict) -> AsyncGenerator[Any]:
        if not self.editing_id:
            yield rx.toast.error(NOT_FOUND, position="top-right")
            return
        async for event in self._save_form(form_data, self.editing_id):
            yield event

    async def _persist(
        self,
        offer_id: int,
        changes: dict[str, Any] | Callable[[OfferEntity], dict[str, Any]],
        message: str,
    ) -> AsyncGenerator[Any]:
        """Apply ``changes`` to a stored offer and show the saved row.

        A callable gets the stored entity, so decisions use fresh data.
        """
        try:
            async with get_asyncdb_session() as session:
                entity = await offer_repo.find_by_id(session, offer_id)
                if entity is None:
                    yield rx.toast.error(NOT_FOUND, position="top-right")
                    return
                values = changes(entity) if callable(changes) else changes
                for key, value in values.items():
                    setattr(entity, key, value)
                await session.commit()
                await session.refresh(entity)
                saved = self._named(entity)
        except Exception:
            logger.exception("Failed to update offer %s", offer_id)
            yield rx.toast.error(ERROR_SAVE, position="top-right")
            return
        self._replace(saved)
        yield rx.toast.info(message, position="top-right")

    @rx.event
    @requires_offer_editor
    async def update_inspected_state(
        self, offer_id: int, value: str | None
    ) -> AsyncGenerator[Any]:
        """Persist a status change; "Versendet" sets today's date if empty."""
        if value not in {s.value for s in OfferStateEnum}:
            yield rx.toast.error("Ungültiger Status.", position="top-right")
            return
        self.date_draft_id = 0

        def changes(entity: OfferEntity) -> dict[str, Any]:
            sent = apply_state_change(entity.state, entity.sent_date, value, _today())
            return {"state": value, "sent_date": sent}

        async for event in self._persist(offer_id, changes, "Status gespeichert."):
            yield event

    @rx.event
    @requires_offer_editor
    async def save_inspected_sent_date(self, offer_id: int) -> AsyncGenerator[Any]:
        """Persist the sent date edited in the inspector."""
        if self.date_draft_id != offer_id:
            return
        try:
            sent = _parse_date(self.date_draft)
        except ValueError:
            self.date_draft_id = 0
            yield rx.toast.error(
                "Bitte ein gültiges Datum eingeben.", position="top-right"
            )
            return
        offer = next((o for o in self.offers if o.id == offer_id), None)
        self.date_draft_id = 0
        if offer is None or offer.sent_date == sent:
            return
        async for event in self._persist(
            offer_id, {"sent_date": sent}, "Datum gespeichert."
        ):
            yield event

    @rx.event
    @requires_offer_editor
    async def archive_offer(self, offer_id: int) -> AsyncGenerator[Any]:
        async for event in self._persist(
            offer_id, {"archived": True}, "Angebot archiviert."
        ):
            yield event

    @rx.event
    @requires_offer_editor
    async def restore_offer(self, offer_id: int) -> AsyncGenerator[Any]:
        async for event in self._persist(
            offer_id, {"archived": False}, "Angebot wiederhergestellt."
        ):
            yield event
