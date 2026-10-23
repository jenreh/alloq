"""State of the story map: grid, selection and the edits of a person."""

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.workshop.entities import Scope
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.map_apply import snapshot_map
from alloq_offer.workshop.services.map_edit import (
    MapConflictError,
    MapEditError,
    MapEditor,
)
from alloq_offer.workshop.services.map_view import NO_SLICE_ID, build_view
from alloq_offer.workshop.states.helpers import current_user_name, open_offer_id
from appkit_commons.database.session import get_asyncdb_session

logger = logging.getLogger(__name__)

SCOPES: list[str] = [scope.value for scope in Scope]
LOAD_ERROR = "Die Story Map konnte nicht geladen werden."
SAVE_ERROR = "Die Änderung konnte nicht gespeichert werden."
NO_TASK = "Diese Aktivität hat noch keine Aufgabe."
SENTENCE_HINT = "Ein Satz aus Rolle, Ziel und Nutzen, ohne Akzeptanzkriterien."

Edit = Callable[[MapEditor], Awaitable[int]]


class MapState(rx.State):
    """The map of the open offer."""

    revision: rx.Field[int] = rx.field(0)
    columns: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    rows: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    stories: rx.Field[dict[str, dict[str, Any]]] = rx.field(default_factory=dict)
    task_options: rx.Field[list[dict[str, str]]] = rx.field(default_factory=list)
    slice_options: rx.Field[list[dict[str, str]]] = rx.field(default_factory=list)
    story_count: rx.Field[int] = rx.field(0)
    selected_id: rx.Field[str] = rx.field("")

    @rx.var
    def has_map(self) -> bool:
        return self.revision > 0

    @rx.var
    def grid_template(self) -> str:
        return f"200px repeat({len(self.columns)}, minmax(230px, 1fr))"

    @rx.var
    def grid_min_width(self) -> str:
        return f"{200 + 230 * len(self.columns)}px"

    @rx.var
    def selected(self) -> dict[str, Any]:
        return self.stories.get(self.selected_id, {})

    @rx.var
    def has_selection(self) -> bool:
        return self.selected_id in self.stories

    @rx.var
    def summary(self) -> str:
        noun = "Story" if self.story_count == 1 else "Stories"
        return (
            f"{len(self.columns)} Aktivitäten · {self.story_count} {noun} · "
            f"Revision {self.revision}"
        )

    async def _reload(self, offer_id: int) -> None:
        async with get_asyncdb_session() as session:
            workspace = await workspace_repo.find_by_offer(session, offer_id)
            if workspace is None:
                return
            view = build_view(await snapshot_map(session, workspace))
            self.revision = workspace.map_revision
        self.columns = view["columns"]
        self.rows = view["rows"]
        self.stories = view["stories"]
        self.task_options = view["task_options"]
        self.slice_options = view["slice_options"]
        self.story_count = view["story_count"]
        if self.selected_id not in self.stories:
            self.selected_id = ""

    async def _apply(self, edit: Edit) -> Any | None:
        """Run one edit; a toast comes back when it did not go through."""
        offer_id = await open_offer_id(self)
        if not offer_id:
            return None
        editor = MapEditor(get_asyncdb_session, offer_id, await current_user_name(self))
        try:
            await edit(editor)
        except MapConflictError as exc:
            await self._reload(offer_id)
            return rx.toast.warning(str(exc), position="top-right")
        except MapEditError as exc:
            return rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Editing the map of offer %s failed", offer_id)
            return rx.toast.error(SAVE_ERROR, position="top-right")
        await self._reload(offer_id)
        return None

    @rx.event
    def select_story(self, story_id: int) -> None:
        if str(story_id) in self.stories:
            self.selected_id = str(story_id)

    @rx.event
    def close_story(self) -> None:
        self.selected_id = ""

    @rx.event
    @requires_offer_editor
    async def load_map(self) -> AsyncGenerator[Any]:
        offer_id = await open_offer_id(self)
        if not offer_id:
            return
        try:
            await self._reload(offer_id)
        except Exception:
            logger.exception("Loading the map of offer %s failed", offer_id)
            yield rx.toast.error(LOAD_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def add_activity(self, form: dict[str, Any]) -> AsyncGenerator[Any]:
        title = str(form.get("title", ""))
        if event := await self._apply(lambda e: e.add_activity(self.revision, title)):
            yield event

    @rx.event
    @requires_offer_editor
    async def rename_activity(
        self, activity_id: int, title: str
    ) -> AsyncGenerator[Any]:
        if event := await self._apply(
            lambda e: e.rename_activity(self.revision, activity_id, title)
        ):
            yield event

    @rx.event
    @requires_offer_editor
    async def move_activity(self, activity_id: int, step: int) -> AsyncGenerator[Any]:
        if event := await self._apply(
            lambda e: e.move_activity(self.revision, activity_id, step)
        ):
            yield event

    @rx.event
    @requires_offer_editor
    async def archive_activity(self, activity_id: int) -> AsyncGenerator[Any]:
        if event := await self._apply(
            lambda e: e.archive_activity(self.revision, activity_id)
        ):
            yield event

    @rx.event
    @requires_offer_editor
    async def add_slice(self, form: dict[str, Any]) -> AsyncGenerator[Any]:
        title = str(form.get("title", ""))
        if event := await self._apply(lambda e: e.add_slice(self.revision, title)):
            yield event

    @rx.event
    @requires_offer_editor
    async def rename_slice(self, slice_id: int, title: str) -> AsyncGenerator[Any]:
        if event := await self._apply(
            lambda e: e.rename_slice(self.revision, slice_id, title)
        ):
            yield event

    @rx.event
    @requires_offer_editor
    async def add_story(self, task_id: int, slice_id: int) -> AsyncGenerator[Any]:
        if not task_id:
            yield rx.toast.error(NO_TASK, position="top-right")
            return
        target = slice_id or None
        if event := await self._apply(
            lambda e: e.add_story(self.revision, task_id, target)
        ):
            yield event

    @rx.event
    @requires_offer_editor
    async def save_story_field(self, name: str, value: str) -> AsyncGenerator[Any]:
        story = self.selected
        if not story or value.strip() == story.get(name, ""):
            return
        story_id = int(self.selected_id)
        if event := await self._apply(
            lambda e: e.update_story(self.revision, story_id, {name: value})
        ):
            yield event

    @rx.event
    @requires_offer_editor
    async def set_scope(self, scope: str) -> AsyncGenerator[Any]:
        if not self.has_selection or scope not in SCOPES:
            return
        story_id = int(self.selected_id)
        if event := await self._apply(
            lambda e: e.set_scope(self.revision, story_id, scope)
        ):
            yield event

    @rx.event
    @requires_offer_editor
    async def place_story(self, task_id: str, slice_id: str) -> AsyncGenerator[Any]:
        """Move the selected story to a task and a slice (``"0"``: none)."""
        if not self.has_selection:
            return
        story_id = int(self.selected_id)
        target = int(slice_id) if slice_id and int(slice_id) != NO_SLICE_ID else None
        if event := await self._apply(
            lambda e: e.move_story(self.revision, story_id, int(task_id), target)
        ):
            yield event

    @rx.event
    @requires_offer_editor
    async def split_selected(self) -> AsyncGenerator[Any]:
        if not self.has_selection:
            return
        story_id = int(self.selected_id)
        if event := await self._apply(lambda e: e.split_story(self.revision, story_id)):
            yield event

    @rx.event
    @requires_offer_editor
    async def archive_selected(self) -> AsyncGenerator[Any]:
        if not self.has_selection:
            return
        story_id = int(self.selected_id)
        event = await self._apply(lambda e: e.archive_story(self.revision, story_id))
        if event:
            yield event
        else:
            self.selected_id = ""
