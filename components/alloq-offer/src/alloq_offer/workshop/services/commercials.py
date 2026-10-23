"""Commercial values of an offer: bound fields, confirmation and its voiding.

Prices and days live in structured fields of the offer. Chapters only reference
them through bound values. A person confirms the current values; any later change
voids that confirmation and flags the chapters that show the values (A09).
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.entities import OfferEntity
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import ChapterEntity, WorkspaceEntity
from alloq_offer.workshop.export.models import ResolvedValue
from alloq_offer.workshop.export.template_package import load_template
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.chapters import (
    current_revisions,
    mark_chapters_review,
)
from alloq_offer.workshop.services.workspace import NO_WORKSPACE

logger = logging.getLogger(__name__)

VOIDED_REASON = "Die bestätigte Kalkulation wurde geändert."
NOT_FOUND = "Das Angebot gibt es nicht mehr."
DAY_FIELDS = ("offer.person_days", "offer.risk_buffer_days")
MONEY_FIELDS = ("offer.production_cost", "offer.recommended_price")


class CommercialsError(ValueError):
    """The values cannot be confirmed; the message is German."""


def _decimal_text(value: Decimal) -> str:
    """German number text with two decimals; ``,00`` is dropped."""
    text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return text.removesuffix(",00")


def _money(value: Decimal, currency: str) -> str:
    symbol = "€" if currency == "EUR" else currency
    return f"{_decimal_text(value)} {symbol}"


def _days_text(value: Decimal) -> str:
    return f"{_decimal_text(value)} PT"


def _plain(value: Decimal) -> str:
    """40.00 and 40 are the same value, so they compare as the same text."""
    return f"{value.normalize():f}"


def current_values(offer: OfferEntity, workspace: WorkspaceEntity) -> dict[str, str]:
    """The raw values as stable strings; what a confirmation is compared with."""
    validity = workspace.validity_date
    return {
        "offer.person_days": _plain(offer.person_days),
        "offer.risk_buffer_days": _plain(offer.risk_buffer_days),
        "offer.production_cost": _plain(offer.production_cost),
        "offer.recommended_price": _plain(offer.recommended_price),
        "workspace.currency": workspace.currency,
        "workspace.validity_date": validity.isoformat() if validity else "",
    }


def is_confirmed(workspace: WorkspaceEntity, values: dict[str, str]) -> bool:
    return (
        workspace.commercials_confirmed_at is not None
        and workspace.commercials_snapshot == values
    )


def resolve_values(
    offer: OfferEntity, workspace: WorkspaceEntity
) -> dict[str, ResolvedValue]:
    """Display texts of the bound fields for the editor and the Word export."""
    confirmed = is_confirmed(workspace, current_values(offer, workspace))
    currency = workspace.currency
    texts: dict[str, str | None] = {
        "offer.person_days": _days_text(offer.person_days),
        "offer.risk_buffer_days": _days_text(offer.risk_buffer_days),
        "offer.production_cost": _money(offer.production_cost, currency),
        "offer.recommended_price": _money(offer.recommended_price, currency),
        "workspace.currency": currency,
        "workspace.validity_date": (
            workspace.validity_date.strftime("%d.%m.%Y")
            if workspace.validity_date
            else None
        ),
    }
    return {
        field: ResolvedValue(text=text, confirmed=confirmed)
        for field, text in texts.items()
    }


@dataclass(frozen=True)
class CommercialsView:
    """What the chapter panel shows about the calculation."""

    rows: list[dict[str, str]]
    confirmed: bool
    confirmed_by: str
    confirmed_at: str
    price_required: bool
    validity_date: str


async def _keys_showing_values(
    session: AsyncSession, workspace: WorkspaceEntity
) -> list[str]:
    """Calc chapters and prose chapters that hold a bound value block."""
    template = load_template(workspace.template_key)
    keys = [c.key for c in template.chapters if c.chapter_type == "calc"]
    prose = {c.key for c in template.chapters if c.chapter_type == "prose"}
    rows = (
        await session.scalars(
            select(ChapterEntity).where(
                ChapterEntity.offer_id == workspace.offer_id,
                ChapterEntity.chapter_key.in_(prose),
            )
        )
    ).all()
    stored = await current_revisions(session, list(rows))
    keys.extend(
        c.chapter_key for c in rows if "bound_value" in str(stored[c.id].content)
    )
    return keys


async def void_if_changed(
    session: AsyncSession, workspace: WorkspaceEntity, offer: OfferEntity
) -> bool:
    """Drop a confirmation whose values changed and flag the chapters showing them."""
    if workspace.commercials_confirmed_at is None:
        return False
    if workspace.commercials_snapshot == current_values(offer, workspace):
        return False
    workspace.commercials_confirmed_at = None
    workspace.commercials_confirmed_by = ""
    workspace.commercials_snapshot = None
    await mark_chapters_review(
        session,
        workspace.offer_id,
        await _keys_showing_values(session, workspace),
        VOIDED_REASON,
    )
    logger.info("Commercial confirmation of offer %s voided", workspace.offer_id)
    return True


async def load_view(session_factory: SessionFactory, offer_id: int) -> CommercialsView:
    async with session_factory() as session:
        workspace, offer = await _open(session, offer_id)
        await void_if_changed(session, workspace, offer)
        resolved = resolve_values(offer, workspace)
        return CommercialsView(
            rows=[
                {"label": label, "value": resolved[field].text or "–"}
                for field, label in _LABELS.items()
            ],
            confirmed=is_confirmed(workspace, current_values(offer, workspace)),
            confirmed_by=workspace.commercials_confirmed_by,
            confirmed_at=(
                workspace.commercials_confirmed_at.strftime("%d.%m.%Y %H:%M")
                if workspace.commercials_confirmed_at
                else ""
            ),
            price_required=workspace.price_required,
            validity_date=(
                workspace.validity_date.isoformat() if workspace.validity_date else ""
            ),
        )


_LABELS = {
    "offer.person_days": "Personentage",
    "offer.risk_buffer_days": "Risikopuffer",
    "offer.production_cost": "Herstellkosten",
    "offer.recommended_price": "Empfohlener Preis",
    "workspace.validity_date": "Bindefrist",
}


async def confirm(
    session_factory: SessionFactory, offer_id: int, user: str, now: datetime
) -> None:
    """Store the current values as confirmed; only this action confirms them."""
    async with session_factory() as session:
        workspace, offer = await _open(session, offer_id)
        workspace.commercials_snapshot = current_values(offer, workspace)
        workspace.commercials_confirmed_by = user
        workspace.commercials_confirmed_at = now


async def _open(
    session: AsyncSession, offer_id: int
) -> tuple[WorkspaceEntity, OfferEntity]:
    workspace = await workspace_repo.find_by_offer(session, offer_id)
    offer = await session.get(OfferEntity, offer_id)
    if workspace is None or offer is None:
        raise CommercialsError(NO_WORKSPACE)
    return workspace, offer


async def set_price_required(
    session_factory: SessionFactory, offer_id: int, required: bool
) -> None:
    async with session_factory() as session:
        workspace, _ = await _open(session, offer_id)
        workspace.price_required = required


async def set_validity_date(
    session_factory: SessionFactory, offer_id: int, validity: date | None
) -> None:
    """Change the Bindefrist; the confirmed values include it, so this voids them."""
    async with session_factory() as session:
        workspace, offer = await _open(session, offer_id)
        workspace.validity_date = validity
        await void_if_changed(session, workspace, offer)


async def void_after_offer_edit(session: AsyncSession, offer: OfferEntity) -> bool:
    """Called where the offer is saved: a changed value voids the confirmation now."""
    workspace = await workspace_repo.find_by_offer(session, offer.id)
    if workspace is None:
        return False
    return await void_if_changed(session, workspace, offer)
