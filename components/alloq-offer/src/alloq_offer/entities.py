"""Offer entity and its enums."""

import enum
from datetime import date
from decimal import Decimal
from typing import Final

from sqlalchemy import Boolean, Date, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import false

from appkit_commons.database.entities import Base, Entity


class OfferStateEnum(enum.StrEnum):
    """State labels of an offer."""

    NEW = "Neu"
    IN_PROGRESS = "In Bearbeitung"
    SENT = "Versendet"


class CustomerIndustryUnit(enum.StrEnum):
    """Customer industry unit (CIU) codes."""

    CP = "CP"
    FS = "FS"
    U = "U"
    P = "P"
    H = "H"
    IMC = "IMC"


CIU_LABELS: Final[dict[str, str]] = {
    CustomerIndustryUnit.CP: "Consumer Services - CP",
    CustomerIndustryUnit.FS: "Financial Services - FS",
    CustomerIndustryUnit.U: "Utilities - U",
    CustomerIndustryUnit.P: "Public - P",
    CustomerIndustryUnit.H: "Health - H",
    CustomerIndustryUnit.IMC: "Industrial Midcaps - IMC",
}


class OfferEntity(Entity, Base):
    """Offer calculated for a customer project."""

    __tablename__ = "offers"
    __table_args__ = (Index("ix_offers_state", "state"),)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    customer: Mapped[str] = mapped_column(String(255), nullable=False)
    person_days: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    risk_buffer_days: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=0
    )
    production_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    recommended_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    key_accounter: Mapped[str] = mapped_column(String(255), nullable=False)
    ciu: Mapped[str] = mapped_column(String(10), nullable=False)
    sharepoint_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    sent_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OfferStateEnum.NEW
    )
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "title": self.title,
            "customer": self.customer,
            "person_days": self.person_days,
            "risk_buffer_days": self.risk_buffer_days,
            "production_cost": self.production_cost,
            "recommended_price": self.recommended_price,
            "key_accounter": self.key_accounter,
            "ciu": self.ciu,
            "sharepoint_url": self.sharepoint_url,
            "sent_date": self.sent_date,
            "state": self.state,
            "archived": bool(self.archived),
            "created": self.created,
            "updated": self.updated,
        }
