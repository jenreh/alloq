from alloq_commons.repositories.absence_repository import (
    AbsenceRepository,
    absence_repo,
)
from alloq_commons.repositories.public_holiday_repository import (
    PublicHolidayRepository,
    public_holiday_repo,
)
from alloq_commons.repositories.capacity_allocation_repository import (
    CapacityAllocationRepository,
    capacity_allocation_repo,
)
from alloq_commons.repositories.capacity_repository import (
    CapacityRepository,
    capacity_repo,
)
from alloq_commons.repositories.employee_repository import (
    EmployeeRepository,
    employee_repo,
)
from alloq_commons.repositories.project_repository import (
    ProjectRepository,
    project_repo,
)
from alloq_commons.repositories.required_capacity_repository import (
    RequiredCapacityRepository,
    required_capacity_repo,
)
from alloq_commons.repositories.risk_repository import RiskRepository, risk_repo
from alloq_commons.repositories.role_repository import RoleRepository, role_repo
from alloq_commons.repositories.status_repository import (
    ProjectStatusRepository,
    status_repo,
)

__all__ = [
    "AbsenceRepository",
    "CapacityAllocationRepository",
    "CapacityRepository",
    "EmployeeRepository",
    "ProjectRepository",
    "ProjectStatusRepository",
    "PublicHolidayRepository",
    "RequiredCapacityRepository",
    "RiskRepository",
    "RoleRepository",
    "absence_repo",
    "capacity_allocation_repo",
    "capacity_repo",
    "employee_repo",
    "project_repo",
    "public_holiday_repo",
    "required_capacity_repo",
    "risk_repo",
    "role_repo",
    "status_repo",
]
