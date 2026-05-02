from alloq_commons.repositories.absence_repository import (
    AbsenceRepository,
    absence_repo,
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
    "CapacityRepository",
    "EmployeeRepository",
    "ProjectRepository",
    "ProjectStatusRepository",
    "RequiredCapacityRepository",
    "RiskRepository",
    "RoleRepository",
    "absence_repo",
    "capacity_repo",
    "employee_repo",
    "project_repo",
    "required_capacity_repo",
    "risk_repo",
    "role_repo",
    "status_repo",
]
