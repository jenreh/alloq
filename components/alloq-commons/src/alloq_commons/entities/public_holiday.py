import logging
from datetime import date

from sqlalchemy import Boolean, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from appkit_commons.database.entities import Base, Entity

logger = logging.getLogger(__name__)


class PublicHolidayEntity(Entity, Base):
    """Public holiday entity for NRW holiday management."""

    __tablename__ = "public_holidays"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    state_code: Mapped[str] = mapped_column(
        String(10), nullable=False, default="NRW", index=True
    )

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "name": self.name,
            "date": self.date,
            "is_recurring": self.is_recurring or False,
            "state_code": self.state_code or "NRW",
            "created": self.created,
            "updated": self.updated,
        }
