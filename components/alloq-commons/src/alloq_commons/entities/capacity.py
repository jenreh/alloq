import logging
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from appkit_commons.database.entities import Base, Entity

logger = logging.getLogger(__name__)


class CapacityEntity(Entity, Base):
    """Actual employee capacity assignment for a project and role."""

    __tablename__ = "capacities"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_capacities_date_range"),
        UniqueConstraint(
            "project_id", "employee_id", "role_id", name="uq_capacities_proj_emp_role"
        ),
    )

    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours_per_week: Mapped[float] = mapped_column(Float, nullable=False, default=40.0)

    project = relationship(
        "ProjectEntity", back_populates="capacities", lazy="selectin"
    )
    employee = relationship("EmployeeEntity", lazy="selectin")
    role = relationship("RoleEntity", lazy="selectin")

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "employee_id": self.employee_id,
            "employee_name": self._employee_name(),
            "role_id": self.role_id,
            "role_name": self.role.name if self.role else "",
            "project_code": self.project.code if self.project else "",
            "project_name": self.project.name_de if self.project else "",
            "start_date": self.start_date,
            "end_date": self.end_date,
            "hours_per_week": self.hours_per_week,
            "created": self.created,
            "updated": self.updated,
        }

    def _employee_name(self) -> str:
        """Return the assigned employee display name."""
        if not self.employee:
            return ""
        return f"{self.employee.first_name} {self.employee.last_name}"
