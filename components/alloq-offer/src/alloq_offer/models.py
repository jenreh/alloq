"""Pydantic models of offers."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from alloq_offer.entities import CustomerIndustryUnit, OfferStateEnum

_Text255 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class Offer(BaseModel):
    """Read model of an offer."""

    id: int = 0
    title: str = ""
    customer: str = ""
    person_days: Decimal = Decimal(0)
    risk_buffer_days: Decimal = Decimal(0)
    production_cost: Decimal = Decimal(0)
    recommended_price: Decimal = Decimal(0)
    key_accounter: str = ""
    ciu: str = ""
    sharepoint_url: str | None = None
    sent_date: date | None = None
    state: str = OfferStateEnum.NEW
    archived: bool = False
    created: datetime | None = None
    updated: datetime | None = None


class OfferCreate(BaseModel):
    """Write model for creating and updating offers."""

    title: _Text255
    customer: _Text255
    person_days: Decimal = Field(..., ge=0, max_digits=8, decimal_places=2)
    risk_buffer_days: Decimal = Field(
        default=Decimal(0), ge=0, max_digits=8, decimal_places=2
    )
    production_cost: Decimal = Field(..., ge=0, max_digits=12, decimal_places=2)
    recommended_price: Decimal = Field(..., ge=0, max_digits=12, decimal_places=2)
    key_accounter: _Text255
    ciu: CustomerIndustryUnit
    sharepoint_url: str | None = Field(default=None, max_length=2048)
    sent_date: date | None = None
    state: OfferStateEnum = OfferStateEnum.NEW

    @field_validator("sharepoint_url")
    @classmethod
    def _check_url(cls, value: str | None) -> str | None:
        """Empty or an http(s) link; empty is stored as None."""
        value = (value or "").strip()
        if not value:
            return None
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("sharepoint_url must start with http:// or https://")
        return value
