import enum
import logging
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from appkit_commons.database.entities import Base, Entity

logger = logging.getLogger(__name__)


class ProjectStateEnum(enum.StrEnum):
    """State labels for a project."""

    PLANNED = "Geplant"
    ACTIVE = "Aktiv"
    AT_RISK = "Risiko"
    COMPLETED = "Abgeschlossen"


project_owners_m2m = Table(
    "project_owners",
    Base.metadata,
    Column(
        "project_id",
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "employee_id",
        Integer,
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class ProjectEntity(Entity, Base):
    """Project entity for resource planning and tracking."""

    __tablename__ = "projects"

    code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    name_de: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ProjectStateEnum.PLANNED
    )
    budget: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#FFD43B")

    owners = relationship(
        "EmployeeEntity",
        secondary=project_owners_m2m,
        lazy="selectin",
    )
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
            "start_date": self.start_date,
            "end_date": self.end_date,
            "state": self.state,
            "budget": self.budget,
            "color": self.color,
            "owner_ids": [owner.id for owner in self.owners] if self.owners else [],
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
