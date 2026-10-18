"""Permission roles of the alloq application (shared by app and components)."""

from alloq_commons.models.department import Department
from appkit_commons.roles import Role

PROJECT_MANAGER_ROLE = Role(
    id=1,
    name="project_manager",
    label="Projektmanager",
    description="Berechtigung für den Projektmanager",
)


ALL_ROLES: list[Role] = [
    PROJECT_MANAGER_ROLE,
]

DEPARTMENT_ROLE_GROUP = "Abteilungen"


def department_role_name(department_id: int) -> str:
    """Permission role name of a department; keyed by id so renames keep it."""
    return f"department_{department_id}"


def department_roles(departments: list[Department]) -> list[Role]:
    """Permission roles offered in user management, one per department."""
    return [
        Role(
            name=department_role_name(d.id),
            label=d.label,
            description=f"Mitglied der Abteilung {d.name}",
            group=DEPARTMENT_ROLE_GROUP,
        )
        for d in departments
    ]
