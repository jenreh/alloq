from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from alloq_commons.entities.employee import SeniorityLevel

STANDARD_WEEKLY_HOURS = 40.0


class Absence(BaseModel):
    """Read model for absence periods."""

    id: int = 0
    employee_id: int = 0
    start_date: date | None = None
    end_date: date | None = None
    created: datetime | None = None
    updated: datetime | None = None


class AbsenceCreate(BaseModel):
    """Write model for creating absence periods."""

    employee_id: int
    start_date: date
    end_date: date


class Employee(BaseModel):
    """Read model for team members."""

    id: int = 0
    first_name: str = ""
    last_name: str = ""
    email: str | None = None
    seniority: str = ""
    job_title: str | None = None
    location: str | None = None
    manager_id: int | None = None
    role_ids: list[int] = []
    role_names: list[str] = []
    absences: list[Absence] = []
    hours_per_week: float = 40.0
    internal_hours: int = 4
    workload_percent: int = 100
    created: datetime | None = None
    updated: datetime | None = None

    def model_post_init(self, __context: Any, /) -> None:
        """Calculate workload percentage from weekly working hours."""
        self.workload_percent = round(
            (self.hours_per_week / STANDARD_WEEKLY_HOURS) * 100
        )


class EmployeeCreate(BaseModel):
    """Write model for creating team members."""

    first_name: str = Field(..., max_length=255)
    last_name: str = Field(..., max_length=255)
    email: str | None = Field(default=None, max_length=255)
    seniority: SeniorityLevel
    job_title: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    manager_id: int | None = None
    role_ids: list[int]
    hours_per_week: float = Field(default=40.0, ge=0)
    internal_hours: int = Field(default=4, ge=0)


class EmployeeUpdate(BaseModel):
    """Write model for updating team members."""

    first_name: str = Field(..., max_length=255)
    last_name: str = Field(..., max_length=255)
    email: str | None = Field(default=None, max_length=255)
    seniority: SeniorityLevel
    job_title: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    manager_id: int | None = None
    role_ids: list[int]
    hours_per_week: float = Field(default=40.0, ge=0)
    internal_hours: int = Field(default=4, ge=0)
