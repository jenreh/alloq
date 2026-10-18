"""Validation state of the project add/edit form."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from importlib import import_module

import reflex as rx
from alloq_commons.entities.project import ProjectStateEnum
from alloq_commons.models.project import Project

DEFAULT_PROJECT_COLOR = "#F7C948"
PROJECT_COLORS = [
    "#F7C948",
    "#7A9A80",
    "#5B7FA3",
    "#D07A55",
    "#C49000",
    "#8D6AA5",
    "#5C9AA4",
    "#B45F83",
    "#6A961E",
    "#3F6070",
]


def _parse_localized_int(value: float | str | None) -> int:
    """Parse German-formatted numbers ("1.123,50"), rounding half up."""
    if isinstance(value, int | float):
        raw = str(value)
    else:
        raw = str(value or 0).strip().replace(".", "").replace(",", ".")
    if not raw:
        return 0
    try:
        return int(Decimal(raw).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:
        raise ValueError(raw) from exc


class ProjectValidationState(rx.State):
    """Validation state for project add forms."""

    form_version: rx.Field[int] = rx.field(0)
    code: rx.Field[str] = rx.field("")
    customer: rx.Field[str] = rx.field("")
    name_de: rx.Field[str] = rx.field("")
    start_date: rx.Field[str] = rx.field("")
    end_date: rx.Field[str] = rx.field("")
    state: rx.Field[str] = rx.field(ProjectStateEnum.PLANNED.value)
    budget: rx.Field[int] = rx.field(0)
    color: rx.Field[str] = rx.field(DEFAULT_PROJECT_COLOR)
    is_internal: rx.Field[bool] = rx.field(False)
    booking_number: rx.Field[str] = rx.field("")
    owner_ids: rx.Field[list[str]] = rx.field(default_factory=list)
    role_capacities: rx.Field[dict[str, int]] = rx.field(default_factory=dict)

    code_error: rx.Field[str] = rx.field("")
    name_de_error: rx.Field[str] = rx.field("")
    date_error: rx.Field[str] = rx.field("")
    budget_error: rx.Field[str] = rx.field("")

    @rx.event(background=True)
    async def initialize(self, project: Project | None = None) -> None:
        """Reset validation state for add mode or preload from a project."""
        # Imported lazily: ProjectState itself imports this module.
        project_state_cls = import_module(
            "alloq_project.states.project_state"
        ).ProjectState
        async with self:
            project_state = await self.get_state(project_state_cls)
            role_caps = {str(role.id): 0 for role in project_state.available_roles}
            if project is None:
                self.code = ""
                self.customer = ""
                self.name_de = ""
                self.start_date = ""
                self.end_date = ""
                self.state = ProjectStateEnum.PLANNED.value
                self.budget = 0
                self.color = DEFAULT_PROJECT_COLOR
                self.is_internal = False
                self.booking_number = ""
                self.owner_ids = []
            else:
                self.code = project.code
                self.customer = project.customer
                self.name_de = project.name_de
                self.start_date = (
                    project.start_date.isoformat() if project.start_date else ""
                )
                self.end_date = project.end_date.isoformat() if project.end_date else ""
                self.state = project.state
                self.budget = project.budget
                self.color = project.color
                self.is_internal = project.is_internal
                self.booking_number = project.booking_number
                self.owner_ids = [str(oid) for oid in project.owner_ids]
                role_caps.update(
                    {
                        str(c.role_id): c.person_days
                        for c in getattr(project, "required_capacities", [])
                    }
                )
            self.role_capacities = role_caps

            self.code_error = ""
            self.name_de_error = ""
            self.date_error = ""
            self.budget_error = ""
            self.form_version += 1

    @rx.event
    def set_code(self, value: str) -> None:
        self.code = value
        self.validate_code()

    @rx.event
    def set_customer(self, value: str) -> None:
        self.customer = value

    @rx.event
    def set_booking_number(self, value: str) -> None:
        self.booking_number = value

    @rx.event
    def set_name_de(self, value: str) -> None:
        self.name_de = value
        self.validate_name_de()

    @rx.event
    def set_start_date(self, value: str) -> None:
        self.start_date = value or ""
        self.validate_dates()

    @rx.event
    def set_end_date(self, value: str) -> None:
        self.end_date = value or ""
        self.validate_dates()

    @rx.event
    def set_state(self, value: str) -> None:
        self.state = value or ProjectStateEnum.PLANNED.value

    @rx.event
    def set_budget(self, value: float | str) -> None:
        try:
            self.budget = _parse_localized_int(value)
        except TypeError, ValueError:
            self.budget = 0
        self.validate_budget()

    @rx.event
    def set_color(self, value: str) -> None:
        self.color = value

    @rx.event
    def set_owner_ids(self, value: list[str]) -> None:
        self.owner_ids = value or []

    @rx.event
    def validate_code(self) -> None:
        self.code_error = "" if self.code.strip() else "Projekt-Code ist erforderlich."

    @rx.event
    def validate_name_de(self) -> None:
        self.name_de_error = (
            "" if self.name_de.strip() else "Name (DE) ist erforderlich."
        )

    @rx.event
    def validate_dates(self) -> None:
        if not self.start_date or not self.end_date:
            self.date_error = "Start und Ende sind erforderlich."
            return
        try:
            if date.fromisoformat(self.end_date[:10]) < date.fromisoformat(
                self.start_date[:10]
            ):
                self.date_error = "Ende darf nicht vor Start liegen."
            else:
                self.date_error = ""
        except ValueError:
            self.date_error = "Bitte gültige Daten auswählen."

    @rx.event
    def validate_budget(self) -> None:
        try:
            budget = _parse_localized_int(self.budget)
        except TypeError, ValueError:
            self.budget_error = "Budget muss eine gültige Zahl sein."
            return
        self.budget_error = "Budget darf nicht negativ sein." if budget < 0 else ""

    @rx.var(cache=True)
    def total_capacity(self) -> int:
        return sum(self.role_capacities.values())

    @rx.event
    def set_role_capacity(self, role_id: str, value: float | str) -> None:
        try:
            self.role_capacities[role_id] = _parse_localized_int(value)
        except TypeError, ValueError:
            self.role_capacities[role_id] = 0

    @rx.event
    def has_errors(self) -> bool:
        return bool(
            self.code_error
            or self.name_de_error
            or self.date_error
            or self.budget_error
        )

    @rx.var
    def is_form_valid(self) -> bool:
        """Check if required fields are complete and valid."""
        try:
            budget_valid = _parse_localized_int(self.budget) >= 0
            dates_valid = bool(self.start_date and self.end_date)
            if dates_valid:
                dates_valid = date.fromisoformat(
                    self.end_date[:10]
                ) >= date.fromisoformat(self.start_date[:10])
        except TypeError, ValueError:
            budget_valid = False
            dates_valid = False

        return bool(
            self.code.strip()
            and self.name_de.strip()
            and budget_valid
            and dates_valid
            and not self.has_errors()
        )

    @rx.var
    def is_form_invalid(self) -> bool:
        return not self.is_form_valid
