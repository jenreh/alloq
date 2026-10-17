from alloq_project.services.planning_builders import without_idle_projects
from alloq_project.states.planning_models import (
    EmployeeAllocationRow,
    GridCell,
    ProjectBlock,
)


def _block(state: str, value: float) -> ProjectBlock:
    row = EmployeeAllocationRow(
        emp_id="e1",
        project_code="P",
        real_id=1,
        name="X",
        cells=[GridCell(key="k", week_key="2026-W01", value=value)],
    )
    return ProjectBlock(code="P", state=state, employees=[row])


def test_idle_planned_and_completed_hidden() -> None:
    blocks = [
        _block("Geplant", 0),
        _block("Abgeschlossen", 0),
        _block("Aktiv", 0),
        _block("Risiko", 0),
        _block("Geplant", 2),
    ]
    result = without_idle_projects(blocks)
    assert [(b.state, b.employees[0].cells[0].value) for b in result] == [
        ("Geplant", 2),
    ]
