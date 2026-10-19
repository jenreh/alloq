"""Price-list documents and fixed-point calculation results."""

from datetime import date
from decimal import Decimal
from typing import Literal, Self
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class PricePosition(BaseModel):
    id: int = 0
    key: str = Field(default_factory=lambda: uuid4().hex)
    la: str = Field("", max_length=50)
    label: str = Field("", max_length=255)
    role_id: int | None = Field(None, gt=0)
    cost: Decimal | None = Field(None, gt=0, le=100_000, decimal_places=2)
    sales_price: Decimal | None = Field(None, gt=0, le=100_000, decimal_places=2)

    def validate_identity(self) -> Self:
        """Permit empty draft rows, but require an identity on save."""
        PositionIdentity(la=self.la, label=self.label)
        return self


class PositionIdentity(BaseModel):
    la: str
    label: str

    @field_validator("label")
    @classmethod
    def _identity(cls, value: str, info: ValidationInfo) -> str:
        if not value.strip() and not info.data["la"].strip():
            raise ValueError("LA or position name required")
        return value


class PriceList(BaseModel):
    id: int = 0
    version: int = 0
    name: str = Field(..., min_length=1, max_length=255)
    as_of: date | None = None
    hours_per_day: Decimal = Field(Decimal("8"), gt=0, le=24, decimal_places=2)
    minimum_margin: Decimal = Field(Decimal("30"), ge=0, le=90, decimal_places=2)
    target_margin: Decimal | None = Field(None, ge=0, le=90, decimal_places=2)
    cost_basis: Literal["hour", "day"] = "day"
    archived: bool = False
    positions: list[PricePosition] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name required")
        return value

    def duplicate(self) -> Self:
        """Independent draft with no persisted identities or archive state."""
        result = self.model_copy(deep=True)
        result.id = result.version = 0
        result.archived = False
        result.name = f"{self.name} (Kopie)"
        for row in result.positions:
            row.id = 0
            row.key = uuid4().hex
        return result


class PricedPosition(BaseModel):
    hourly_cost: Decimal | None = None
    daily_cost: Decimal | None = None
    minimum_daily: Decimal | None = None
    minimum_hourly: Decimal | None = None
    daily_sales: Decimal | None = None
    hourly_sales: Decimal | None = None
    below_minimum: bool = False


class PriceGridRow(BaseModel):
    key: str
    role_id: str = ""
    below_minimum: bool = False
    effective_sales: str = ""
    cell_values: dict[str, str]
    display: dict[str, str]
