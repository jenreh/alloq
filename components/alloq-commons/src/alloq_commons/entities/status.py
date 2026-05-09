import logging
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from appkit_commons.database.entities import Base, Entity

logger = logging.getLogger(__name__)


class ProjectStatusEntity(Entity, Base):
    """Status snapshot for project progress history."""

    __tablename__ = "project_statuses"

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    budget_spent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    budget: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    earned_value: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
    )
    actual_cost: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
    )
    eac_linear: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    eac_additive: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
    )

    project = relationship("ProjectEntity", back_populates="statuses")

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "status_date": self.status_date.isoformat() if self.status_date else "",
            "progress": self.progress,
            "budget_spent": self.budget_spent,
            "notes": self.notes or "",
            "budget": self.budget or 0.0,
            "earned_value": self.earned_value or 0.0,
            "actual_cost": self.actual_cost or 0.0,
            "eac_linear": self.eac_linear or 0.0,
            "eac_additive": self.eac_additive or 0.0,
            "created": self.created,
            "updated": self.updated,
        }
