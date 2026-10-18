"""Filters of the planning page; mixed into `PlanningStore`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import reflex as rx

PROJECT_VIEW = "Projekte"
GRID_VIEW = "Grid"
EMPLOYEE_PARAM = "employee"


class PlanningFilterMixin(rx.State, mixin=True):
    """Project, role, employee and scope filters shared by all planning views.

    A mixin rather than a substate: the filtered views of `PlanningStore` read
    these vars next to its entity caches.
    """

    if TYPE_CHECKING:  # Provided by PlanningStore.
        view_mode: str
        current_employee_id: int | None
        _filters_focused: bool

        def _store_view_settings(self) -> Any: ...

    project_filter: rx.Field[list[str]] = rx.field(default_factory=list)
    role_filter: rx.Field[list[str]] = rx.field(default_factory=list)
    employee_filter: rx.Field[list[str]] = rx.field(default_factory=list)
    available_only: rx.Field[bool] = rx.field(False)
    hide_internal: rx.Field[bool] = rx.field(False)
    project_scope: rx.Field[bool] = rx.field(False)
    employee_scope: rx.Field[bool] = rx.field(False)

    @rx.event
    def set_project_filter(self, value: list[str]) -> None:
        self.project_filter = value

    @rx.event
    def set_role_filter(self, value: list[str]) -> None:
        self.role_filter = value

    @rx.event
    def set_employee_filter(self, value: list[str]) -> None:
        self.employee_filter = value

    @rx.event
    def set_available_only(self, value: bool) -> None:
        self.available_only = value

    @rx.event
    def set_hide_internal(self, value: bool) -> None:
        self.hide_internal = value

    @rx.event
    def open_project(self, project_id: int) -> Any:
        """Open the project view filtered to one project, clearing other filters."""
        self._clear_filters()
        self.view_mode = PROJECT_VIEW
        self.project_filter = [str(project_id)]
        return rx.redirect("/plan")

    def _focus_employee_from_url(self) -> Any:
        """Show only the employee named in `?employee=`, clearing other filters."""
        employee_id = self.router.url.query_parameters.get(EMPLOYEE_PARAM, "")
        if not employee_id.isdigit():
            return None
        self._clear_filters()
        self.view_mode = GRID_VIEW
        self.employee_filter = [employee_id]
        # Drop the param so a later reload keeps the user's own filters.
        return rx.call_script(
            "window.history.replaceState(null, '', window.location.pathname)"
        )

    def _clear_filters(self) -> None:
        self.project_filter = []
        self.role_filter = []
        self.employee_filter = []
        self.available_only = False
        self.hide_internal = False
        self.project_scope = False
        self.employee_scope = False
        # The next settings read keeps the scopes off and stores that.
        self._filters_focused = True

    @rx.event
    def toggle_project_scope(self) -> Any:
        if not self.project_scope and self.current_employee_id is None:
            return self._notify_no_employee()
        self.project_scope = not self.project_scope
        return self._store_view_settings()

    @rx.event
    def toggle_employee_scope(self) -> Any:
        if not self.employee_scope and self.current_employee_id is None:
            return self._notify_no_employee()
        self.employee_scope = not self.employee_scope
        return self._store_view_settings()

    @staticmethod
    def _notify_no_employee() -> Any:
        return rx.toast.warning(
            "Ihrem Benutzer ist kein Mitarbeiter zugeordnet.", position="top-right"
        )

    @rx.var(cache=True)
    def project_filter_label(self) -> str:
        c = len(self.project_filter)
        return f'"Projekte ({c})"' if c > 0 else ""

    @rx.var(cache=True)
    def role_filter_label(self) -> str:
        c = len(self.role_filter)
        return f'"Rollen ({c})"' if c > 0 else ""

    @rx.var(cache=True)
    def employee_filter_label(self) -> str:
        c = len(self.employee_filter)
        return f'"MA ({c})"' if c > 0 else ""
