"""Employees read projects and planning; edit controls need the project manager role."""

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
MANAGER = '"project_manager"'


def _editor_guarded(component: rx.Component, marker: str) -> bool:
    """``component`` renders ``marker`` only for the project manager role."""
    # rx.cond wraps its Cond in a Fragment.
    cond = str(component.children[0].cond)
    return (
        marker in str(component)
        and MANAGER in cond
        and EMPLOYEE not in cond
        and "is_admin" not in cond
    )


class TestPlanningPage:
    def test_grid_is_read_only_without_the_manager_role(self) -> None:
        rendered = str(planning_excel_grid(grid_id="g"))
        assert "readOnly:!" in rendered.replace(" ", "")
        assert MANAGER in rendered
        assert "is_admin" not in rendered

    def test_save_and_create_buttons_need_the_manager_role(self) -> None:
        assert _editor_guarded(planning_toolbar()[-1], "Projekt planen")

    def test_absence_lane_has_a_disabled_flag(self) -> None:
        assert "disabled" in _AbsenceLane.get_props()


class TestProjectsPage:
    def test_create_button_needs_the_manager_role(self) -> None:
        assert _editor_guarded(project_toolbar()[-1], "Projekt anlegen")

    def test_drawer_tabs_are_disabled_without_the_manager_role(self) -> None:
        rendered = str(project_detail_drawer())
        assert "fieldset" in rendered
        assert MANAGER in rendered

    def test_tab_edit_actions_check_the_manager_role(self) -> None:
        for tab in (status_tab(), risiken_tab(), ressourcen_tab()):
            assert MANAGER in str(tab)
            assert "is_admin" not in str(tab)
