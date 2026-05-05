from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from alloq_commons.entities.project import ProjectStateEnum


class RequiredCapacity(BaseModel):
    """Read model for required project staffing by role."""

    id: int = 0
    project_id: int = 0
    role_id: int = 0
    role_name: str = ""
    person_days: int = 0
    created: datetime | None = None
    updated: datetime | None = None


class RequiredCapacityCreate(BaseModel):
    """Write model for required capacity."""

    project_id: int = 0
    role_id: int
    person_days: int = Field(..., ge=0)


class RequiredCapacityUpdate(RequiredCapacityCreate):
    """Write model for updating required capacity."""


class ProjectStatus(BaseModel):
    """Read model for project status history entries."""

    id: int = 0
    project_id: int = 0
    status_date: date | None = None
    fortschritt: int = 0
    budget_verbrauch: int = 0
    created: datetime | None = None
    updated: datetime | None = None


class ProjectStatusCreate(BaseModel):
    """Write model for project status history entries."""

    project_id: int
    status_date: date
    fortschritt: int = Field(default=0, ge=0, le=100)
    budget_verbrauch: int = Field(default=0, ge=0, le=100)


class ProjectStatusUpdate(ProjectStatusCreate):
    """Write model for updating project status entries."""


class Risk(BaseModel):
    """Read model for project risks."""

    id: int = 0
    project_id: int = 0
    name: str = ""
    description: str = ""
    severity: str = "medium"
    probability: str = "medium"
    impact: str = "medium"
    mitigation_status: str = "open"
    owner: str | None = None
    created: datetime | None = None
    updated: datetime | None = None


class RiskCreate(BaseModel):
    """Write model for project risks."""

    project_id: int
    name: str = Field(..., max_length=255)
    description: str = Field(default="", max_length=2000)
    severity: str = "medium"
    probability: str = "medium"
    impact: str = "medium"
    mitigation_status: str = "open"
    owner: str | None = Field(default=None, max_length=255)


class RiskUpdate(RiskCreate):
    """Write model for updating project risks."""


class Capacity(BaseModel):
    """Read model for actual employee project capacity."""

    id: int = 0
    project_id: int = 0
    employee_id: int = 0
    employee_name: str = ""
    role_id: int = 0
    role_name: str = ""
    project_code: str = ""
    project_name: str = ""
    start_date: date | None = None
    end_date: date | None = None
    hours_per_week: float = 40.0
    created: datetime | None = None
    updated: datetime | None = None


class CapacityCreate(BaseModel):
    """Write model for actual employee project capacity."""

    project_id: int
    employee_id: int
    role_id: int
    start_date: date
    end_date: date
    hours_per_week: float = Field(default=40.0, ge=0)


class CapacityUpdate(CapacityCreate):
    """Write model for updating actual capacity."""


class CapacityAllocation(BaseModel):
    """Read model for one weekly per-employee project allocation."""

    id: int = 0
    project_id: int = 0
    employee_id: int = 0
    role_id: int = 0
    role_name: str = ""
    week_start: date | None = None
    person_days: float = 0.0
    created: datetime | None = None
    updated: datetime | None = None


class CapacityAllocationCreate(BaseModel):
    """Write model for one weekly per-employee project allocation."""

    project_id: int
    employee_id: int
    role_id: int
    week_start: date
    person_days: float = Field(default=0.0, ge=0)


class CapacityAllocationUpdate(CapacityAllocationCreate):
    """Write model for updating a weekly allocation."""


class TeamMemberBadge(BaseModel):
    """Minimal read model for a team member badge in a project card."""

    initials: str = ""
    name: str = ""


class Project(BaseModel):
    """Read model for projects."""

    id: int = 0
    code: str = ""
    customer: str = ""
    name_de: str = ""
    start_date: date | None = None
    end_date: date | None = None
    state: str = ProjectStateEnum.PLANNED
    budget: int = 0
    color: str = "#FFD43B"
    owner_ids: list[int] = []
    current_progress: int = 0
    current_spent: int = 0
    team_initials: list[str] = []
    team_members: list[TeamMemberBadge] = []
    risk_count: int = 0
    required_capacities: list[RequiredCapacity] = []
    created: datetime | None = None
    updated: datetime | None = None

    @property
    def team_count(self) -> int:
        """Return the number of unique team members."""
        return len(self.team_initials)


class ProjectCreate(BaseModel):
    """Write model for creating projects."""

    code: str = Field(..., min_length=1, max_length=50)
    customer: str = Field(..., min_length=1, max_length=255)
    name_de: str = Field(..., min_length=1, max_length=255)
    start_date: date
    end_date: date
    state: str = Field(default=ProjectStateEnum.PLANNED, max_length=20)
    budget: int = Field(..., ge=0)
    color: str = Field(default="#FFD43B", max_length=7)
    owner_ids: list[int] = []
    required_capacities: list[RequiredCapacityCreate] = []

    @model_validator(mode="after")
    def validate_date_range(self) -> "ProjectCreate":
        """Validate start and end dates."""
        if self.end_date < self.start_date:
            raise ValueError("End date must not be before start date")
        return self


class ProjectUpdate(ProjectCreate):
    """Write model for updating projects."""
