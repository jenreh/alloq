import enum
import logging

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from appkit_commons.database.entities import Base, Entity

logger = logging.getLogger(__name__)


class RiskLevel(enum.StrEnum):
    """Risk level values."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskMitigationStatus(enum.StrEnum):
    """Risk mitigation status values."""

    OPEN = "open"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"


class RiskEntity(Entity, Base):
    """Project risk tracking entity."""

    __tablename__ = "risks"

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    probability: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    impact: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mitigation_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="Offen"
    )
    measures: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    project = relationship("ProjectEntity", back_populates="risks")

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description or "",
            "probability": self.probability,
            "impact": self.impact,
            "mitigation_status": self.mitigation_status,
            "measures": self.measures or "",
            "created": self.created,
            "updated": self.updated,
        }
