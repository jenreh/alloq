"""Employees read projects and planning; edit controls are for admins only."""

import reflex as rx
from alloq_project.components.planning_gantt import _AbsenceLane
from alloq_project.components.planning_shared import planning_excel_grid
from alloq_project.components.planning_toolbar import planning_toolbar
from alloq_project.components.project_overview import project_detail_drawer
from alloq_project.components.project_resource_tab import ressourcen_tab
from alloq_project.components.project_risk_tab import risiken_tab
from alloq_project.components.project_status_tab import status_tab
from alloq_project.components.project_toolbar import project_toolbar

EMPLOYEE = '"employee"'


def _admin_guarded(component: rx.Component, marker: str) -> bool:
    """``component`` renders ``marker`` only behind the admin flag."""
    # rx.cond wraps its Cond in a Fragment.
    cond = str(component.children[0].cond)  # ty: ignore[unresolved-attribute]
    return marker in str(component) and "is_admin" in cond and EMPLOYEE not in cond


class TestPlanningPage:
    def test_grid_is_read_only_for_non_admins(self) -> None:
        rendered = str(planning_excel_grid(grid_id="g"))
        assert "readOnly:!" in rendered.replace(" ", "")
        assert "is_admin" in rendered

    def test_save_and_create_buttons_are_admin_only(self) -> None:
        assert _admin_guarded(planning_toolbar()[-1], "Projekt planen")

    def test_absence_lane_has_a_disabled_flag(self) -> None:
        assert "disabled" in _AbsenceLane.get_props()


class TestProjectsPage:
    def test_create_button_is_admin_only(self) -> None:
        assert _admin_guarded(project_toolbar()[-1], "Projekt anlegen")

    def test_drawer_tabs_are_disabled_for_non_admins(self) -> None:
        rendered = str(project_detail_drawer())
        assert "fieldset" in rendered
        assert "is_admin" in rendered

    def test_tab_edit_actions_check_the_admin_flag(self) -> None:
        for tab in (status_tab(), risiken_tab(), ressourcen_tab()):
            assert "is_admin" in str(tab)
