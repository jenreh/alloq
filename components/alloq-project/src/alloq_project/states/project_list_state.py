"""Project list: filter, grouping and the row shown in the inspector."""

import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

import reflex as rx
from alloq_commons.entities.project import ProjectStateEnum
from alloq_commons.models.project import Project
from alloq_commons.repositories import project_repo

from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.decorators import requires_admin

logger = logging.getLogger(__name__)

FILTER_ALL = "Alle"
FILTER_MINE = "Meine"
FILTERS: list[str] = [
    FILTER_ALL,
    FILTER_MINE,
    ProjectStateEnum.ACTIVE.value,
    ProjectStateEnum.PLANNED.value,
    ProjectStateEnum.AT_RISK.value,
]
STATUS_TONES: dict[str, str] = {
    ProjectStateEnum.ACTIVE.value: "positive",
    ProjectStateEnum.PLANNED.value: "info",
    ProjectStateEnum.AT_RISK.value: "negative",
    ProjectStateEnum.COMPLETED.value: "neutral",
}


def status_tone(state: str) -> str:
    return STATUS_TONES.get(state, "neutral")


def _matches(project: Project, list_filter: str) -> bool:
    if list_filter in (FILTER_ALL, FILTER_MINE):
        return True
    return project.state == list_filter


class ProjectListState(rx.State, mixin=True):
    """List filter, selection and inspector; mixed into `ProjectState`.

    A mixin rather than a substate: its computed vars read `ProjectState`
    vars, and a substate would have to exist wherever `ProjectState` is used.
    """

    if TYPE_CHECKING:  # Provided by ProjectState.
        projects: list[Project]
        my_projects: list[Project]
        other_projects: list[Project]
        selected_project: Project | None

        def _upsert_project(self, project: Project) -> None: ...

    list_filter: str = FILTER_ALL
    inspected_id: int = 0
    inspector_open: str = rx.LocalStorage("1", name="alloq_projects_inspector")

    @rx.event
    def set_list_filter(self, value: str) -> None:
        self.list_filter = value if value in FILTERS else FILTER_ALL

    @rx.event
    def inspect(self, project_id: int) -> None:
        self.inspected_id = project_id

    @rx.event
    def toggle_inspector(self) -> None:
        self.inspector_open = "0" if self.inspector_open == "1" else "1"

    @rx.var
    def show_inspector(self) -> bool:
        return self.inspector_open == "1"

    @rx.var
    def mine_rows(self) -> list[Project]:
        return [p for p in self.my_projects if _matches(p, self.list_filter)]

    @rx.var
    def other_rows(self) -> list[Project]:
        if self.list_filter == FILTER_MINE:
            return []
        return [p for p in self.other_projects if _matches(p, self.list_filter)]

    @rx.var
    def row_count(self) -> int:
        return len(self.mine_rows) + len(self.other_rows)

    @rx.var
    def visible_total_pt(self) -> int:
        return sum(project.total_pt for project in (*self.mine_rows, *self.other_rows))

    @rx.var
    def inspected(self) -> Project | None:
        """The selected project, else the first row."""
        rows = [*self.mine_rows, *self.other_rows]
        return next((p for p in rows if p.id == self.inspected_id), None) or (
            rows[0] if rows else None
        )

    @rx.var
    def inspected_tone(self) -> str:
        return status_tone(self.inspected.state) if self.inspected else "neutral"

    @rx.var
    def subtitle(self) -> str:
        active = sum(
            1
            for p in self.projects
            if p.state in (ProjectStateEnum.ACTIVE, ProjectStateEnum.AT_RISK)
        )
        at_risk = sum(1 for p in self.projects if p.state == ProjectStateEnum.AT_RISK)
        return f"{len(self.projects)} Projekte · {active} aktiv · {at_risk} gefährdet"

    def _apply_project_state(self, project_id: int, value: str) -> None:
        """Show a saved status in the list and an open project drawer."""
        project = next((p for p in self.projects if p.id == project_id), None)
        if project:
            self._upsert_project(project.model_copy(update={"state": value}))
        if self.selected_project and self.selected_project.id == project_id:
            self.selected_project = self.selected_project.model_copy(
                update={"state": value}
            )

    @rx.event
    @requires_admin
    async def update_inspected_project_state(
        self, project_id: int, value: str | None
    ) -> AsyncGenerator[Any]:
        """Persist a project status change made in the project inspector."""
        valid_states = {state.value for state in ProjectStateEnum}
        if value is None or value not in valid_states:
            yield rx.toast.error("Ungültiger Projektstatus.", position="top-right")
            return

        try:
            async with get_asyncdb_session() as session:
                entity = await project_repo.find_by_id(session, project_id)
                if not entity:
                    yield rx.toast.error(
                        "Projekt nicht gefunden.", position="top-right"
                    )
                    return
                entity.state = value
                await session.commit()

            self._apply_project_state(project_id, value)
            yield rx.toast.info("Status gespeichert.", position="top-right")
        except Exception as exc:
            logger.error("Failed to update project %s status: %s", project_id, exc)
            yield rx.toast.error(
                "Projektstatus konnte nicht gespeichert werden.",
                position="top-right",
            )
