from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

MAX_PRICE = 100_000
MAX_CONTRIBUTION_MARGIN_PERCENT = 90


class DailyRate(BaseModel):
    """Read model for the daily rate of a role, with its derived prices.

    ``list_price`` holds a manual list price (None = calculated); the
    ``recommended_*`` and ``effective_list_price`` fields are the prices in effect.
    """

    id: int = 0
    role_id: int = 0
    role_name: str = ""
    production_cost: int | None = None
    list_price: int | None = None
    recommended_price: int | None = None
    recommended_margin: int | None = None
    recommended_share: int | None = None
    calculated_list_price: int | None = None
    effective_list_price: int | None = None
    list_margin: int | None = None
    list_share: int | None = None
    created: datetime | None = None
    updated: datetime | None = None


class DailyRateUpdate(BaseModel):
    """Write model for the prices of a daily rate; None clears a price."""

    production_cost: int | None = Field(None, gt=0, le=MAX_PRICE)
    list_price: int | None = Field(None, gt=0, le=MAX_PRICE)

    @property
    def is_empty(self) -> bool:
        """True when no price is set, so the rate can be removed."""
        return self.production_cost is None and self.list_price is None


class DailyRateSettingsUpdate(BaseModel):
    """Write model for the margins shared by all roles."""

    min_contribution_margin_percent: int = Field(
        ..., ge=0, le=MAX_CONTRIBUTION_MARGIN_PERCENT
    )
    contribution_margin_percent: int = Field(
        ..., ge=0, le=MAX_CONTRIBUTION_MARGIN_PERCENT
    )

    @model_validator(mode="after")
    def _minimum_not_above_margin(self) -> Self:
        if self.min_contribution_margin_percent > self.contribution_margin_percent:
            msg = "minimal margin above margin"
            raise ValueError(msg)
        return self
