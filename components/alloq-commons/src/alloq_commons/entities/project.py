import enum
import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from appkit_commons.database.entities import Base, Entity

if TYPE_CHECKING:
    from alloq_commons.entities.employee import EmployeeEntity

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
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_projects_date_range"),
    )

    code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    customer: Mapped[str] = mapped_column(String(255), nullable=True, default="")
    name_de: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ProjectStateEnum.PLANNED
    )
    budget: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#FFD43B")
    is_internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    ev_earned_value: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
    )
    ev_actual_cost: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
    )
    ev_eac_linear: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
    )
    ev_eac_additive: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
    )

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
    capacity_allocations = relationship(
        "CapacityAllocationEntity",
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
            "customer": self.customer or "",
            "name_de": self.name_de,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "state": self.state,
            "budget": self.budget,
            "color": self.color,
            "is_internal": bool(self.is_internal),
            "owner_ids": [owner.id for owner in self.owners] if self.owners else [],
            "current_progress": latest_status.progress if latest_status else 0,
            "current_spent": latest_status.budget_spent if latest_status else 0,
            "team_initials": self._team_initials(),
            "team_members": self._team_members(),
            "risk_count": len(self.risks) if self.risks else 0,
            "required_capacities": [
                capacity.to_dict() for capacity in self.required_capacities
            ]
            if self.required_capacities
            else [],
            "ev_earned_value": self.ev_earned_value or 0.0,
            "ev_actual_cost": self.ev_actual_cost or 0.0,
            "ev_eac_linear": self.ev_eac_linear or 0.0,
            "ev_eac_additive": self.ev_eac_additive or 0.0,
            "created": self.created,
            "updated": self.updated,
        }

    def _staffed_employee_capacity(self) -> list[tuple[EmployeeEntity, float]]:
        """Return project members and planned PT from the project's start week."""
        if not self.start_date or not self.end_date:
            return []

        first_week = self.start_date - timedelta(days=self.start_date.weekday())
        last_week = self.end_date - timedelta(days=self.end_date.weekday())
        planned_by_employee: dict[int, tuple[EmployeeEntity, float]] = {}
        for allocation in self.capacity_allocations or []:
            employee = allocation.employee
            week_start = allocation.week_start
            person_days = allocation.person_days or 0.0
            if (
                not employee
                or employee.id is None
                or week_start is None
                or not first_week <= week_start <= last_week
                or person_days <= 0
            ):
                continue
            _, planned = planned_by_employee.get(employee.id, (employee, 0.0))
            planned_by_employee[employee.id] = (employee, planned + person_days)
        return [
            (employee, round(planned_pt, 2))
            for employee, planned_pt in planned_by_employee.values()
        ]

    def _team_initials(self) -> list[str]:
        """Return unique initials of employees with non-zero allocations."""
        return [
            f"{employee.first_name[:1]}{employee.last_name[:1]}"
            for employee, _ in self._staffed_employee_capacity()
        ]

    def _team_members(self) -> list[dict]:
        """Return team members with planned person-days in the project period."""
        return [
            {
                "initials": f"{employee.first_name[:1]}{employee.last_name[:1]}",
                "name": f"{employee.first_name} {employee.last_name}",
                "planned_pt": planned_pt,
            }
            for employee, planned_pt in self._staffed_employee_capacity()
        ]
