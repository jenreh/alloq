from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from appkit_commons.database.entities import Base, Entity

DEFAULT_CONTRIBUTION_MARGIN_PERCENT = 35
DEFAULT_MIN_CONTRIBUTION_MARGIN_PERCENT = 30


class DailyRateEntity(Entity, Base):
    """Daily rate of a role; empty prices mean "not set"."""

    __tablename__ = "daily_rates"

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    production_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    list_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """Manual list price; empty means it is calculated."""

    role = relationship("RoleEntity", lazy="selectin")

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "role_id": self.role_id,
            "role_name": self.role.name if self.role else "",
            "production_cost": self.production_cost,
            "list_price": self.list_price,
            "created": self.created,
            "updated": self.updated,
        }


class DailyRateSettingsEntity(Entity, Base):
    """Settings shared by all daily rates; the table holds a single row."""

    __tablename__ = "daily_rate_settings"

    min_contribution_margin_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_MIN_CONTRIBUTION_MARGIN_PERCENT
    )
    """Margin of the recommended sales price."""
    contribution_margin_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_CONTRIBUTION_MARGIN_PERCENT
    )
    """Margin of the list price."""

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "min_contribution_margin_percent": self.min_contribution_margin_percent,
            "contribution_margin_percent": self.contribution_margin_percent,
            "created": self.created,
            "updated": self.updated,
        }
