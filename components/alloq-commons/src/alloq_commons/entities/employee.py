import datetime
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
    PROFESSIONAL = "Professional"
    EXPERT = "Expert"


class EmployeeEntity(Entity, Base):
    """Team member entity for resource planning."""

    __tablename__ = "employees"

    first_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    seniority: Mapped[str] = mapped_column(String(50), nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hours_per_week: Mapped[float] = mapped_column(Float, nullable=False, default=40.0)
    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )

    roles = relationship("RoleEntity", secondary=employee_roles, lazy="selectin")
    absences = relationship(
        "AbsenceEntity", lazy="selectin", cascade="all, delete-orphan"
    )
    manager = relationship(
        "EmployeeEntity",
        remote_side="EmployeeEntity.id",
        backref="direct_reports",
        lazy="selectin",
    )

    def to_dict(self) -> dict:
        """Convert entity to dictionary for Pydantic model creation."""

        absences = []
        if getattr(self, "absences", None):
            today = datetime.datetime.now(datetime.UTC).date()
            valid_absences = [
                a
                for a in self.absences
                if a.start_date and a.end_date and a.end_date >= today
            ]
            valid_absences.sort(key=lambda a: a.start_date)
            absences = [a.to_dict() for a in valid_absences]
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "seniority": self.seniority,
            "job_title": self.job_title,
            "location": self.location,
            "manager_id": self.manager_id,
            "role_ids": [r.id for r in self.roles] if self.roles else [],
            "role_names": [r.name for r in self.roles] if self.roles else [],
            "absences": absences,
            "hours_per_week": self.hours_per_week,
            "created": self.created,
            "updated": self.updated,
        }
