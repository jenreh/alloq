import logging
from collections.abc import AsyncGenerator
from typing import Any, Literal

import reflex as rx
from alloq_commons.entities import DailyRateEntity
from alloq_commons.entities.daily_rate import (
    DEFAULT_CONTRIBUTION_MARGIN_PERCENT,
    DEFAULT_MIN_CONTRIBUTION_MARGIN_PERCENT,
)
from alloq_commons.models import (
    DailyRate,
    DailyRateSettingsUpdate,
    DailyRateUpdate,
    Role,
)
from alloq_commons.models.daily_rate import (
    MAX_CONTRIBUTION_MARGIN_PERCENT,
    MAX_PRICE,
)
from alloq_commons.repositories import daily_rate_repo, role_repo
from alloq_commons.services.daily_rate_pricing import price_rate
from pydantic import ValidationError

from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.decorators import requires_admin

logger = logging.getLogger(__name__)

PriceField = Literal["production_cost", "list_price"]
PRICE_FIELDS: tuple[PriceField, ...] = ("production_cost", "list_price")

INVALID_PRICE_MESSAGE = f"Preise müssen zwischen 1 und {MAX_PRICE} € liegen."
INVALID_MARGIN_MESSAGE = (
    f"Deckungsbeiträge müssen zwischen 0 und {MAX_CONTRIBUTION_MARGIN_PERCENT} % "
    "liegen, der Mindest-DB darf nicht über dem DB liegen."
)


def _whole_number(value: float | str) -> int:
    """Number input value as whole number; empty or invalid input is 0."""
    try:
        return round(float(value))
    except TypeError, ValueError:
        return 0


def _parse_euros(value: float | str | None) -> int | None:
    """Whole euros from a formatted input ("1.120 €"); None when empty."""
    if isinstance(value, int | float):
        return round(value)
    digits = "".join(c for c in str(value or "") if c.isdigit())
    return int(digits) if digits else None


def _clamp_margin(value: int) -> int:
    return min(max(value, 0), MAX_CONTRIBUTION_MARGIN_PERCENT)


class DailyRateState(rx.State):
    """State for the daily rates (Tagessätze) of all roles."""

    rates: rx.Field[list[DailyRate]] = rx.field(default_factory=list)
    roles: rx.Field[list[Role]] = rx.field(default_factory=list)
    min_margin: rx.Field[int] = rx.field(DEFAULT_MIN_CONTRIBUTION_MARGIN_PERCENT)
    margin: rx.Field[int] = rx.field(DEFAULT_CONTRIBUTION_MARGIN_PERCENT)
    min_margin_draft: rx.Field[int] = rx.field(DEFAULT_MIN_CONTRIBUTION_MARGIN_PERCENT)
    margin_draft: rx.Field[int] = rx.field(DEFAULT_CONTRIBUTION_MARGIN_PERCENT)
    is_loading: rx.Field[bool] = rx.field(False)
    search_filter: rx.Field[str] = rx.field("")
    form_version: rx.Field[int] = rx.field(0)

    @rx.var
    def rows(self) -> list[DailyRate]:
        """One priced row per role, filtered by role name.

        Prices follow the margin inputs while they are typed.
        """
        by_role = {rate.role_id: rate for rate in self.rates}
        minimum = _clamp_margin(self.min_margin_draft)
        margin = _clamp_margin(self.margin_draft)
        search = self.search_filter.lower()
        return [
            price_rate(
                by_role.get(role.id, DailyRate(role_id=role.id)), minimum, margin
            ).model_copy(update={"role_name": role.name})
            for role in self.roles
            if search in role.name.lower()
        ]

    @rx.event
    def set_search_filter(self, value: str) -> None:
        """Update the search filter."""
        self.search_filter = value

    @rx.event
    def set_min_margin_draft(self, value: float | str) -> None:
        """Keep the minimal margin input until it is saved."""
        self.min_margin_draft = _whole_number(value)

    @rx.event
    def set_margin_draft(self, value: float | str) -> None:
        """Keep the margin input until it is saved."""
        self.margin_draft = _whole_number(value)

    async def _load_rates(self) -> None:
        async with get_asyncdb_session() as session:
            entities = await daily_rate_repo.find_all_by_role_name(session)
            self.rates = [DailyRate(**e.to_dict()) for e in entities]

    async def _load(self) -> None:
        async with get_asyncdb_session() as session:
            entities = await daily_rate_repo.find_all_by_role_name(session)
            roles = await role_repo.find_all_paginated(session)
            minimum, margin = await daily_rate_repo.get_margins(session)
            self.rates = [DailyRate(**e.to_dict()) for e in entities]
            self.roles = [Role(**r.to_dict()) for r in roles]
        self._set_margins(minimum, margin)

    def _set_margins(self, minimum: int, margin: int) -> None:
        self.min_margin = self.min_margin_draft = minimum
        self.margin = self.margin_draft = margin
        self.form_version += 1

    @rx.event
    @requires_admin
    async def load_daily_rates(self) -> AsyncGenerator[Any]:
        """Load roles, their rates and the margins.

        The loading row only replaces the table on the first load; revisits
        refresh the existing rows in place to avoid a flicker.
        """
        if not self.roles:
            self.is_loading = True
            yield
        try:
            await self._load()
        except Exception:
            logger.exception("Failed to load daily rates")
            yield rx.toast.error(
                "Fehler beim Laden der Tagessätze.", position="top-right"
            )
        finally:
            self.is_loading = False

    @rx.event
    @requires_admin
    async def save_margins(self) -> AsyncGenerator[Any]:
        """Store both margins once an input loses focus."""
        drafts = (self.min_margin_draft, self.margin_draft)
        if drafts == (self.min_margin, self.margin):
            return
        try:
            data = DailyRateSettingsUpdate(
                min_contribution_margin_percent=self.min_margin_draft,
                contribution_margin_percent=self.margin_draft,
            )
            async with get_asyncdb_session() as session:
                await daily_rate_repo.save_margins(
                    session,
                    data.min_contribution_margin_percent,
                    data.contribution_margin_percent,
                )
        except ValidationError:
            self._set_margins(self.min_margin, self.margin)
            yield rx.toast.error(INVALID_MARGIN_MESSAGE, position="top-right")
            return
        except Exception:
            logger.exception("Failed to save contribution margins")
            self._set_margins(self.min_margin, self.margin)
            yield rx.toast.error(
                "Fehler beim Speichern der Deckungsbeiträge.", position="top-right"
            )
            return
        self.min_margin = data.min_contribution_margin_percent
        self.margin = data.contribution_margin_percent
        yield rx.toast.info("Deckungsbeiträge gespeichert.", position="top-right")

    @rx.event
    @requires_admin
    async def save_production_cost(
        self, role_id: int, value: float | str
    ) -> AsyncGenerator[Any]:
        """Store the production cost of a role."""
        async for event in self._save_price(role_id, "production_cost", value):
            yield event

    @rx.event
    @requires_admin
    async def save_list_price(
        self, role_id: int, value: float | str
    ) -> AsyncGenerator[Any]:
        """Store a manual list price; the calculated price clears it."""
        async for event in self._save_price(role_id, "list_price", value):
            yield event

    def _row(self, role_id: int) -> DailyRate:
        return next(
            (row for row in self.rows if row.role_id == role_id),
            DailyRate(role_id=role_id),
        )

    def _new_price(
        self, row: DailyRate, field: PriceField, value: float | str
    ) -> int | None:
        """Parsed input; a manual price equal to the calculated one is cleared."""
        price = _parse_euros(value)
        if field == "list_price" and price == row.calculated_list_price:
            return None
        return price

    async def _save_price(
        self, role_id: int, field: PriceField, value: float | str
    ) -> AsyncGenerator[Any]:
        row = self._row(role_id)
        price = self._new_price(row, field, value)
        if getattr(row, field) == price:
            return
        try:
            async with get_asyncdb_session() as session:
                entity = await daily_rate_repo.find_by_role_id(session, role_id)
                values = {f: getattr(entity, f) for f in PRICE_FIELDS} if entity else {}
                data = DailyRateUpdate(**{**values, field: price})
                if entity is None:
                    await daily_rate_repo.create(
                        session, DailyRateEntity(role_id=role_id, **data.model_dump())
                    )
                elif data.is_empty:
                    await daily_rate_repo.delete_by_id(session, entity.id)
                else:
                    setattr(entity, field, getattr(data, field))
                    await daily_rate_repo.update(session, entity)
        except ValidationError:
            self.form_version += 1
            yield rx.toast.error(INVALID_PRICE_MESSAGE, position="top-right")
            return
        except Exception:
            logger.exception("Failed to save %s of role %d", field, role_id)
            self.form_version += 1
            yield rx.toast.error(
                "Fehler beim Speichern des Tagessatzes.", position="top-right"
            )
            return
        await self._load_rates()
