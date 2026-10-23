"""Offer and industry entities and the offer state enum."""

import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import false

from appkit_commons.database.entities import Base, Entity


class OfferStateEnum(enum.StrEnum):
    """State labels of an offer."""

    NEW = "Neu"
    IN_PROGRESS = "In Bearbeitung"
    SENT = "Versendet"


class IndustryEntity(Entity, Base):
    """Customer industry (Branche) of an offer; admins maintain the list."""

    __tablename__ = "industries"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "name": self.name,
            "created": self.created,
            "updated": self.updated,
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
    industry_id: Mapped[int] = mapped_column(
        ForeignKey("industries.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sharepoint_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    sent_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OfferStateEnum.NEW
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    """Project created when the offer was accepted."""
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
            "industry_id": self.industry_id,
            "sharepoint_url": self.sharepoint_url,
            "sent_date": self.sent_date,
            "state": self.state,
            "archived": bool(self.archived),
            "project_id": self.project_id,
            "created": self.created,
            "updated": self.updated,
        }
