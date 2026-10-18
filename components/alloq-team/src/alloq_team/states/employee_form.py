from alloq_commons.models.department import Department
from alloq_commons.models.employee import EmployeeCreate


def employee_from_form(form_data: dict) -> EmployeeCreate:
    """Parse the add/edit employee form into an EmployeeCreate model."""
    raw_roles = form_data.get("role_ids", [])
    if isinstance(raw_roles, str):
        role_ids = [int(x) for x in raw_roles.split(",") if x]
    else:
        role_ids = [int(x) for x in raw_roles]

    key_role_id = int(form_data["key_role_id"])
    role_ids = [key_role_id, *(r for r in role_ids if r != key_role_id)]

    manager_id_raw = form_data.get("manager_id")
    department_raw = form_data.get("department_id")
    return EmployeeCreate(
        first_name=form_data.get("first_name", "").strip(),
        last_name=form_data.get("last_name", "").strip(),
        email=form_data.get("email", "").strip() or None,
        seniority=form_data.get("seniority", "Advanced"),
        job_title=form_data.get("job_title", "").strip() or None,
        location=form_data.get("location", "").strip() or None,
        department_id=int(department_raw) if department_raw else None,
        manager_id=int(manager_id_raw) if manager_id_raw else None,
        key_role_id=key_role_id,
        role_ids=role_ids,
        hours_per_week=float(form_data.get("hours_per_week", 40.0)),
        # The field is optional in the form; a cleared input posts "".
        internal_hours=int(form_data.get("internal_hours") or 0),
    )


def default_department_id(departments: list[Department]) -> str:
    """Preselect the department of a new employee when there is only one."""
    return str(departments[0].id) if len(departments) == 1 else ""
