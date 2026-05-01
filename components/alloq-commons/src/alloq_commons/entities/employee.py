import enum
import logging

from sqlalchemy import Column, Float, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from appkit_commons.database.entities import Base, Entity

logger = logging.getLogger(__name__)


# Many-to-many association table
employee_roles = Table(
    "employee_roles",
    Base.metadata,
    Column(
        "employee_id",
        Integer,
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class SeniorityLevel(enum.StrEnum):
    """Seniority levels for team members."""

    ADVANCED = "Advanced"
    SENIOR = "Senior"
    EXPERT = "Expert"


class EmployeeEntity(Entity, Base):
    """Team member entity for resource planning."""

    __tablename__ = "employees"

    first_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    seniority: Mapped[str] = mapped_column(String(50), nullable=False)
    hours_per_week: Mapped[float] = mapped_column(Float, nullable=False, default=40.0)

    roles = relationship("RoleEntity", secondary=employee_roles, lazy="selectin")

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "seniority": self.seniority,
            "role_ids": [r.id for r in self.roles] if self.roles else [],
            "role_names": [r.name for r in self.roles] if self.roles else [],
            "hours_per_week": self.hours_per_week,
            "created": self.created,
            "updated": self.updated,
        }
