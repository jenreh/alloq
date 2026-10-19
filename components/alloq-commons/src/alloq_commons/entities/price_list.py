"""Independent price-list headers and ordered rate positions."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from appkit_commons.database.entities import Base, Entity


class PriceListEntity(Entity, Base):
    __tablename__ = "price_lists"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    cost_basis: Mapped[str] = mapped_column(String(4), nullable=False, default="day")
    hours_per_day: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=8)
    minimum_margin: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=30)
    target_margin: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    positions: Mapped[list[PricePositionEntity]] = relationship(
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="PricePositionEntity.sort_order",
    )

    def to_dict(self) -> dict:
        return {
            key: getattr(self, key)
            for key in (
                "id",
                "name",
                "as_of",
                "cost_basis",
                "hours_per_day",
                "minimum_margin",
                "target_margin",
                "archived",
                "version",
            )
        } | {"positions": [row.to_dict() for row in self.positions]}


class PricePositionEntity(Entity, Base):
    __tablename__ = "price_positions"

    price_list_id: Mapped[int] = mapped_column(
        ForeignKey("price_lists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    la: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    label: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    role_id: Mapped[int | None] = mapped_column(
        ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sales_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    def to_dict(self) -> dict:
        return {
            key: getattr(self, key)
            for key in (
                "id",
                "la",
                "label",
                "role_id",
                "cost",
                "sales_price",
            )
        } | {"key": str(self.id)}
