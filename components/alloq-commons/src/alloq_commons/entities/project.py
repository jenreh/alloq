import logging
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from appkit_commons.database.entities import Base, Entity

logger = logging.getLogger(__name__)


class ProjectEntity(Entity, Base):
    """Project entity for resource planning and tracking."""

    __tablename__ = "projects"

    code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    name_de: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    budget: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#FFD43B")
    created_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_by = relationship("EmployeeEntity", lazy="selectin")
    statuses = relationship(
        "ProjectStatusEntity",
        lazy="selectin",
        cascade="all, delete-orphan",
        back_populates="project",
        order_by="ProjectStatusEntity.status_date.desc()",
    )
    risks = relationship(
        "RiskEntity",
        lazy="selectin",
        cascade="all, delete-orphan",
        back_populates="project",
    )
    capacities = relationship(
        "CapacityEntity",
        lazy="selectin",
        cascade="all, delete-orphan",
        back_populates="project",
    )
    required_capacities = relationship(
        "RequiredCapacityEntity",
        lazy="selectin",
        cascade="all, delete-orphan",
        back_populates="project",
    )

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        latest_status = self.statuses[0] if self.statuses else None
        return {
            "id": self.id,
            "code": self.code,
            "name_de": self.name_de,
            "name_en": self.name_en,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "budget": self.budget,
            "color": self.color,
            "created_by_id": self.created_by_id,
            "created_by_name": self._created_by_name(),
            "current_progress": latest_status.fortschritt if latest_status else 0,
            "current_spent": latest_status.budget_verbrauch if latest_status else 0,
            "team_initials": self._team_initials(),
            "risk_count": len(self.risks) if self.risks else 0,
            "required_capacities": [
                capacity.to_dict() for capacity in self.required_capacities
            ]
            if self.required_capacities
            else [],
            "created": self.created,
            "updated": self.updated,
        }

    def _created_by_name(self) -> str:
        """Return the project lead display name."""
        if not self.created_by:
            return ""
        return f"{self.created_by.first_name} {self.created_by.last_name}"

    def _team_initials(self) -> list[str]:
        """Return unique initials of employees with project capacity."""
        initials = []
        seen_employee_ids = set()
        for capacity in self.capacities or []:
            employee = capacity.employee
            if not employee or employee.id in seen_employee_ids:
                continue
            seen_employee_ids.add(employee.id)
            initials.append(f"{employee.first_name[:1]}{employee.last_name[:1]}")
        return initials
