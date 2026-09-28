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


class CapacityAllocationEntity(Entity, Base):
    """Weekly per-employee allocation of a project (person days for one week)."""

    __tablename__ = "capacity_allocations"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "employee_id",
            "role_id",
            "week_start",
            name="uq_capacity_alloc_proj_emp_role_week",
        ),
        CheckConstraint("person_days >= 0", name="ck_capacity_allocations_person_days"),
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
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    person_days: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Not eager: loading a week range must not pull every allocated project
    # together with that project's whole allocation history.
    project = relationship(
        "ProjectEntity", back_populates="capacity_allocations", lazy="raise_on_sql"
    )
    employee = relationship("EmployeeEntity", lazy="selectin")
    role = relationship("RoleEntity", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "employee_id": self.employee_id,
            "role_id": self.role_id,
            "role_name": self.role.name if self.role else "",
            "week_start": self.week_start,
            "person_days": self.person_days,
            "created": self.created,
            "updated": self.updated,
        }
