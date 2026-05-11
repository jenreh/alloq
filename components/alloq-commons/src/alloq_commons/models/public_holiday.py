from datetime import UTC, datetime
from datetime import date as date_type

from pydantic import BaseModel, Field


def _today() -> date_type:
    return datetime.now(tz=UTC).date()


class PublicHoliday(BaseModel):
    """Read model for public holidays."""

    id: int = 0
    name: str = ""
    date: date_type = Field(default_factory=_today)
    is_recurring: bool = False
    state_code: str = "NRW"
    created: datetime | None = None
    updated: datetime | None = None


class PublicHolidayCreate(BaseModel):
    """Write model for creating/updating public holidays."""

    name: str = Field(..., max_length=255)
    date: date_type
    is_recurring: bool = False
    state_code: str = Field(default="NRW", max_length=10)
