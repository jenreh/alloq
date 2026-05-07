import logging
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
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
    fortschritt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    budget_verbrauch: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    anmerkung: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    project = relationship("ProjectEntity", back_populates="statuses")

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "status_date": self.status_date.isoformat() if self.status_date else "",
            "fortschritt": self.fortschritt,
            "budget_verbrauch": self.budget_verbrauch,
            "anmerkung": self.anmerkung or "",
            "created": self.created,
            "updated": self.updated,
        }
