from datetime import date, datetime

from alloq_commons.entities.employee import SeniorityLevel
from pydantic import BaseModel, Field


class Employee(BaseModel):
    """Read model for team members."""

    id: int = 0
    first_name: str = ""
    last_name: str = ""
    seniority: str = ""
    role_ids: list[int] = []
    role_names: list[str] = []
    hours_per_week: float = 40.0
    created: datetime | None = None
    updated: datetime | None = None


class EmployeeCreate(BaseModel):
    """Write model for creating team members."""

    first_name: str = Field(..., max_length=255)
    last_name: str = Field(..., max_length=255)
    seniority: SeniorityLevel
    role_ids: list[int]
    hours_per_week: float = Field(default=40.0, ge=0)


class EmployeeUpdate(BaseModel):
    """Write model for updating team members."""

    first_name: str = Field(..., max_length=255)
    last_name: str = Field(..., max_length=255)
    seniority: SeniorityLevel
    role_ids: list[int]
    hours_per_week: float = Field(default=40.0, ge=0)


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
