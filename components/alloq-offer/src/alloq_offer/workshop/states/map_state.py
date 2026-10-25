"""State of the story map: grid, selection and the edits of a person."""

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from functools import wraps
from typing import Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.map_apply import snapshot_map
from alloq_offer.workshop.services.map_edit import (
    MapConflictError,
    MapEditError,
    MapEditor,
)
from alloq_offer.workshop.services.map_view import (
    NO_SLICE_ID,
    build_view,
    filter_archived,
    filter_rows,
    list_rows,
)
from alloq_offer.workshop.services.story_rules import parse_story_sentence
from alloq_offer.workshop.states.helpers import current_user_name, open_offer_id
from appkit_commons.database.session import get_asyncdb_session

logger = logging.getLogger(__name__)

COLUMN_PX = 230
INSERT_ACTIVITY = "activity"
INSERT_SLICE = "slice"
VIEW_MAP = "map"
VIEW_LIST = "list"
VIEWS = [{"value": VIEW_MAP, "label": "Map"}, {"value": VIEW_LIST, "label": "Liste"}]
LIST_COLUMNS = ("title", "story", "description")
SAVED = "Story gespeichert."
REJECTED_FORMAT = (
    "{count} Eingaben nicht übernommen. Die User Story braucht die Form "
    "„Als … möchte ich …, um …“."
)
LOAD_ERROR = "Die Story Map konnte nicht geladen werden."
SAVE_ERROR = "Die Änderung konnte nicht gespeichert werden."
NO_TASK = "Diese Aktivität hat noch keine Aufgabe."
PICK_TASK = "Bitte wählen Sie eine Aufgabe für die Story."
RESTORED = "Story wiederhergestellt."
SENTENCE_HINT = "Ein Satz aus Rolle, Ziel und Nutzen, ohne Akzeptanzkriterien."

Edit = Callable[[MapEditor], Awaitable[int]]


def _rejected_toast(count: int) -> Any:
    return rx.toast.warning(REJECTED_FORMAT.format(count=count), position="top-right")


def _busy[F: Callable[..., Any]](func: F) -> F:
    """Show the saving bar while an edit handler runs.

    The bare ``yield`` sends the flag before the database work starts; the
    final delta (new map and ``saving`` off) arrives together.
    """

    @wraps(func)
    async def wrapper(self: MapState, *args: Any, **kwargs: Any) -> Any:
        self.saving = True
        yield
        try:
            async for item in func(self, *args, **kwargs):
                yield item
        finally:
            self.saving = False
            self.saving_cell = ""

    return wrapper  # type: ignore[return-value]


def _count_label(name: str, picked: list[str]) -> str:
    """CSS content for the count pill of a filter select, empty when unused."""
    return f'"{name} ({len(picked)})"' if picked else ""


class MapState(rx.State):
    """The map of the open offer."""

    revision: rx.Field[int] = rx.field(0)
    map_loaded: rx.Field[bool] = rx.field(False)
    """False until the map of the open offer arrived; the page shows a skeleton."""
    saving: rx.Field[bool] = rx.field(False)
    saving_cell: rx.Field[str] = rx.field("")
    """``<task>:<slice>`` of the cell whose new story is being saved."""
    _loaded_offer: int = 0
    columns: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    _rows: list[dict[str, Any]] = []
    _stories: dict[str, dict[str, Any]] = {}
    """Backend only: ``visible_rows`` and ``selected`` send what the page shows."""
    task_options: rx.Field[list[dict[str, str]]] = rx.field(default_factory=list)
    task_groups: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    slice_options: rx.Field[list[dict[str, str]]] = rx.field(default_factory=list)
    story_count: rx.Field[int] = rx.field(0)
    archived: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    archive_open: rx.Field[bool] = rx.field(False)
    archive_search: rx.Field[str] = rx.field("")
    restore_tasks: rx.Field[dict[str, str]] = rx.field(default_factory=dict)
    """Target task per archived story id, as far as the person changed it."""
    selected_id: rx.Field[str] = rx.field("")
    drawer_wide: rx.Field[bool] = rx.field(False)
    map_search: rx.Field[str] = rx.field("")
    search_epoch: rx.Field[int] = rx.field(0)
    """Bumped by a filter reset so the uncontrolled search field starts empty."""
    slice_filter: rx.Field[list[str]] = rx.field(default_factory=list)
    skeleton_only: rx.Field[bool] = rx.field(False)
    view: rx.Field[str] = rx.field(VIEW_MAP)
    insert_at: rx.Field[str] = rx.field("")
    collapsed_slices: rx.Field[list[str]] = rx.field(default_factory=list)
    """Edge whose insert popup is open, e.g. ``activity:2`` or ``slice:0``."""

    @rx.var
    def has_map(self) -> bool:
        return self.revision > 0

    @rx.var
    def archive_label(self) -> str:
        return f"Archiv ({len(self.archived)})"

    @rx.var
    def archived_rows(self) -> list[dict[str, Any]]:
        return self._archive_entries() if self.archive_open else []

    def _archive_entries(self) -> list[dict[str, Any]]:
        live = {option["value"] for option in self.task_options}

        def target(story: dict[str, Any]) -> str:
            old = story["task_id"] if story["task_id"] in live else ""
            return self.restore_tasks.get(str(story["id"]), old)

        return filter_archived(
            [{**story, "task": target(story)} for story in self.archived],
            self.archive_search,
        )

    @rx.var
    def is_filtered(self) -> bool:
        return bool(self.map_search.strip() or self.slice_filter or self.skeleton_only)

    @rx.var
    def list_rows(self) -> list[dict[str, Any]]:
        if self.view != VIEW_LIST:
            return []
        return list_rows(self.columns, self.visible_rows, self._stories)

    @rx.var
    def slice_filter_label(self) -> str:
        return _count_label("Schnitte", self.slice_filter)

    @rx.var
    def visible_rows(self) -> list[dict[str, Any]]:
        return filter_rows(
            self._rows,
            search=self.map_search,
            slice_ids=self.slice_filter,
            skeleton_only=self.skeleton_only,
        )

    @rx.var
    def grid_template(self) -> str:
        """One resizable track per activity (see ``column_width``)."""
        return " ".join(
            f"var(--grid-col-{column['id']}, {COLUMN_PX}px)" for column in self.columns
        )

    @rx.var
    def selected(self) -> dict[str, Any]:
        return self._stories.get(self.selected_id, {})

    @rx.var
    def has_selection(self) -> bool:
        return self.selected_id in self._stories

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
            snapshot = await snapshot_map(session, workspace)
            revision = workspace.map_revision
        self._show(offer_id, snapshot, revision)

    def _show(self, offer_id: int, snapshot: dict, revision: int) -> None:
        """Take a map snapshot into the vars the page renders."""
        view = build_view(snapshot)
        self.revision = revision
        self._loaded_offer = offer_id
        self.map_loaded = True
        self.columns = view["columns"]
        self._rows = view["rows"]
        self._stories = view["stories"]
        self.task_options = view["task_options"]
        self.slice_options = view["slice_options"]
        self.story_count = view["story_count"]
        self.task_groups = view["task_groups"]
        self.archived = view["archived"]
        kept = {str(story["id"]) for story in self.archived}
        self.restore_tasks = {k: v for k, v in self.restore_tasks.items() if k in kept}
        if self.selected_id not in self._stories:
            self.selected_id = ""

    async def _apply(self, edit: Edit) -> Any | None:
        """Run one edit; a toast comes back when it did not go through."""
        offer_id = await open_offer_id(self)
        if not offer_id:
            return None
        editor = MapEditor(get_asyncdb_session, offer_id, await current_user_name(self))
        try:
            revision = await edit(editor)
        except MapConflictError as exc:
            await self._reload(offer_id)
            return rx.toast.warning(str(exc), position="top-right")
        except MapEditError as exc:
            return rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Editing the map of offer %s failed", offer_id)
            return rx.toast.error(SAVE_ERROR, position="top-right")
        if editor.snapshot is None:
            await self._reload(offer_id)
        else:
            self._show(offer_id, editor.snapshot, revision)
        return None

    @rx.event
    def select_story(self, story_id: int) -> None:
        if str(story_id) in self._stories:
            self.selected_id = str(story_id)

    @rx.event
    def close_story(self) -> None:
        self.selected_id = ""

    @rx.event
    def toggle_drawer_width(self) -> None:
        self.drawer_wide = not self.drawer_wide

    @rx.event
    def set_view(self, value: str) -> None:
        if value in (VIEW_MAP, VIEW_LIST):
            self.view = value

    @rx.event
    def notify_rejected(self, count: int) -> Any:
        return _rejected_toast(count)

    @rx.event
    def toggle_slice(self, slice_id: int) -> None:
        key = str(slice_id)
        if key in self.collapsed_slices:
            self.collapsed_slices = [k for k in self.collapsed_slices if k != key]
        else:
            self.collapsed_slices = [*self.collapsed_slices, key]

    @rx.event
    def open_archive(self) -> None:
        self.archive_open = True

    @rx.event
    def close_archive(self) -> None:
        self.archive_open = False
        self.archive_search = ""
        self.restore_tasks = {}

    @rx.event
    def set_archive_search(self, value: str) -> None:
        self.archive_search = value

    @rx.event
    def set_restore_task(self, story_id: int, value: str) -> None:
        self.restore_tasks = {**self.restore_tasks, str(story_id): value}

    @rx.event
    def open_insert(self, edge: str) -> None:
        self.insert_at = edge

    @rx.event
    def close_insert(self) -> None:
        self.insert_at = ""

    @rx.event
    def set_map_search(self, value: str) -> None:
        self.map_search = value

    @rx.event
    def set_slice_filter(self, value: list[str]) -> None:
        self.slice_filter = value

    @rx.event
    def set_skeleton_only(self, value: bool) -> None:
        self.skeleton_only = value

    @rx.event
    def reset_filters(self) -> None:
        self.map_search = ""
        self.search_epoch += 1
        self.slice_filter = []
        self.skeleton_only = False

    @rx.event
    @requires_offer_editor
    async def load_map(self) -> AsyncGenerator[Any]:
        offer_id = await open_offer_id(self)
        if not offer_id:
            return
        if offer_id != self._loaded_offer:
            self.map_loaded = False
            yield
        try:
            await self._reload(offer_id)
        except Exception:
            logger.exception("Loading the map of offer %s failed", offer_id)
            yield rx.toast.error(LOAD_ERROR, position="top-right")
        self.map_loaded = True

    async def _insert(self, kind: str, title: str, index: int | None) -> Any | None:
        """Add an activity or slice at ``index``; a done insert closes the popup."""
        add = MapEditor.add_activity if kind == INSERT_ACTIVITY else MapEditor.add_slice
        event = await self._apply(lambda e: add(e, self.revision, title, index))
        if event is None:
            self.insert_at = ""
        return event

    @rx.event
    @requires_offer_editor
    @_busy
    async def submit_insert(self, form: dict[str, Any]) -> AsyncGenerator[Any]:
        """Popup on a grid edge: kind and position come from ``insert_at``.

        The form sends only the name, because Reflex moves a form's submit
        handler out of the ``rx.foreach`` that renders the edge.
        """
        kind, _, index = self.insert_at.partition(":")
        if kind not in (INSERT_ACTIVITY, INSERT_SLICE) or not index.isdigit():
            return
        if event := await self._insert(kind, str(form.get("title", "")), int(index)):
            yield event

    @rx.event
    @requires_offer_editor
    @_busy
    async def add_activity(
        self, form: dict[str, Any], index: int | None = None
    ) -> AsyncGenerator[Any]:
        title = str(form.get("title", ""))
        if event := await self._insert(INSERT_ACTIVITY, title, index):
            yield event

    @rx.event
    @requires_offer_editor
    @_busy
    async def rename_activity(
        self, activity_id: int, title: str
    ) -> AsyncGenerator[Any]:
        # The title wraps over two lines in the header but stays one line.
        name = " ".join(title.split())
        if event := await self._apply(
            lambda e: e.rename_activity(self.revision, activity_id, name)
        ):
            yield event

    @rx.event
    @requires_offer_editor
    @_busy
    async def move_activity(self, activity_id: int, step: int) -> AsyncGenerator[Any]:
        if event := await self._apply(
            lambda e: e.move_activity(self.revision, activity_id, step)
        ):
            yield event

    @rx.event
    @requires_offer_editor
    @_busy
    async def archive_activity(self, activity_id: int) -> AsyncGenerator[Any]:
        if event := await self._apply(
            lambda e: e.archive_activity(self.revision, activity_id)
        ):
            yield event

    @rx.event
    @requires_offer_editor
    @_busy
    async def add_slice(
        self, form: dict[str, Any], index: int | None = None
    ) -> AsyncGenerator[Any]:
        title = str(form.get("title", ""))
        if event := await self._insert(INSERT_SLICE, title, index):
            yield event

    @rx.event
    @requires_offer_editor
    @_busy
    async def rename_slice(self, slice_id: int, title: str) -> AsyncGenerator[Any]:
        if event := await self._apply(
            lambda e: e.rename_slice(self.revision, slice_id, title)
        ):
            yield event

    @rx.event
    @requires_offer_editor
    @_busy
    async def delete_slice(self, slice_id: int) -> AsyncGenerator[Any]:
        if event := await self._apply(
            lambda e: e.delete_slice(self.revision, slice_id)
        ):
            yield event

    @rx.event
    @requires_offer_editor
    @_busy
    async def add_story(self, form: dict[str, Any]) -> AsyncGenerator[Any]:
        """Quick add in a map cell; task and slice come as hidden form fields.

        Reflex moves a form's submit handler out of the ``rx.foreach`` that
        renders the cell, so the cell's ids travel in the form, not the call.
        """
        task_id = str(form.get("task_id", ""))
        slice_id = str(form.get("slice_id", ""))
        if not task_id.isdigit() or not int(task_id) or not slice_id.isdigit():
            yield rx.toast.error(NO_TASK, position="top-right")
            return
        title = str(form.get("title", ""))
        target = int(slice_id) or None
        self.saving_cell = f"{task_id}:{slice_id}"
        yield
        if event := await self._apply(
            lambda e: e.add_story(self.revision, int(task_id), target, title)
        ):
            yield event

    @rx.event
    @requires_offer_editor
    @_busy
    async def save_story(self, form: dict[str, Any]) -> AsyncGenerator[Any]:
        """Save the inspector form of the selected story."""
        if not self.has_selection:
            return
        story_id = int(self.selected_id)
        # Title and story parts wrap in the inspector but stay one line.
        fields = {
            name: str(value) if name == "description" else " ".join(str(value).split())
            for name, value in form.items()
        }
        before = self.revision
        if event := await self._apply(
            lambda e: e.update_story(self.revision, story_id, fields)
        ):
            yield event
        elif self.revision != before:
            yield rx.toast.success(SAVED, position="top-right")

    @rx.event
    @requires_offer_editor
    @_busy
    async def apply_list_changes(
        self, changes: list[dict[str, Any]]
    ) -> AsyncGenerator[Any]:
        """Save cells edited in the list; keys are ``<story id>|<column>``."""
        fields: dict[int, dict[str, str]] = {}
        rejected = 0
        for change in changes:
            story_id, _, column = str(change.get("key", "")).partition("|")
            value = str(change.get("value", ""))
            if column not in LIST_COLUMNS:
                continue
            if story_id not in self._stories:
                rejected += 1
                continue
            if column == "story":
                parts = parse_story_sentence(value)
                if parts is None:
                    rejected += 1
                    continue
                update = dict(zip(("role", "goal", "benefit"), parts, strict=True))
            else:
                update = {column: value}
            fields.setdefault(int(story_id), {}).update(update)
        if fields and (
            event := await self._apply(
                lambda e: e.update_stories(self.revision, fields)
            )
        ):
            yield event
        if rejected:
            yield _rejected_toast(rejected)

    @rx.event
    @requires_offer_editor
    @_busy
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
    @_busy
    async def split_selected(self) -> AsyncGenerator[Any]:
        if not self.has_selection:
            return
        story_id = int(self.selected_id)
        if event := await self._apply(lambda e: e.split_story(self.revision, story_id)):
            yield event

    @rx.event
    @requires_offer_editor
    @_busy
    async def archive_selected(self) -> AsyncGenerator[Any]:
        if not self.has_selection:
            return
        story_id = int(self.selected_id)
        event = await self._apply(lambda e: e.archive_story(self.revision, story_id))
        if event:
            yield event
        else:
            self.selected_id = ""

    @rx.event
    @requires_offer_editor
    @_busy
    async def restore_story(self, story_id: int) -> AsyncGenerator[Any]:
        """Bring an archived story back under its chosen live task."""
        row = next((r for r in self._archive_entries() if r["id"] == story_id), None)
        if row is None:
            return
        if not row["task"]:
            yield rx.toast.error(PICK_TASK, position="top-right")
            return
        task_id = int(row["task"])
        if event := await self._apply(
            lambda e: e.unarchive_story(self.revision, story_id, task_id)
        ):
            yield event
        else:
            yield rx.toast.success(RESTORED, position="top-right")
