"""State of the "Entwurf" tab: stage progress, counts and open decisions."""

import logging
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.workshop.services import draft_overview
from alloq_offer.workshop.services.map_edit import (
    MapConflictError,
    MapEditError,
    MapEditor,
)
from alloq_offer.workshop.states.briefing_state import BriefingState
from alloq_offer.workshop.states.chapter_state import ChapterState
from alloq_offer.workshop.states.export_state import ExportState
from alloq_offer.workshop.states.helpers import current_user_name, open_offer_id
from alloq_offer.workshop.states.map_state import MapState
from alloq_offer.workshop.states.review_state import ReviewState
from alloq_offer.workshop.states.sources_state import SourcesState
from appkit_commons.database.session import get_asyncdb_session

logger = logging.getLogger(__name__)

LOAD_ERROR = "Der Stand des Entwurfs konnte nicht geladen werden."
SCOPE_CONFIRMED = "Der vorgeschlagene Umfang ist jetzt angeboten."
SCOPE_ERROR = "Der Umfang konnte nicht bestätigt werden."
REFRESH = [
    SourcesState.load_sources,
    MapState.load_map,
    BriefingState.load_briefing,
    ChapterState.load_chapters,
    ReviewState.run_checks,
    ExportState.load_exports,
]


class DraftState(rx.State):
    """Progress of the one-click draft and the decisions it leaves to people."""

    stages: rx.Field[list[dict[str, str]]] = rx.field(default_factory=list)
    decisions: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    activities: rx.Field[int] = rx.field(0)
    stories: rx.Field[int] = rx.field(0)
    offered: rx.Field[int] = rx.field(0)
    chapters_written: rx.Field[int] = rx.field(0)
    chapters_total: rx.Field[int] = rx.field(0)
    map_revision: rx.Field[int] = rx.field(0)
    draft_export_id: rx.Field[int] = rx.field(0)
    working: rx.Field[bool] = rx.field(False)

    @rx.var
    def started(self) -> bool:
        """The pipeline ran or runs: any stage after reading the sources moved."""
        return any(stage["status"] != draft_overview.OPEN for stage in self.stages[1:])

    @rx.var
    def pipeline_progress(self) -> int:
        """Finished stages of the one-click draft, in percent."""
        if not self.stages:
            return 0
        done = sum(s["status"] == draft_overview.DONE for s in self.stages)
        return round(100 * done / len(self.stages))

    @rx.var
    def has_draft_file(self) -> bool:
        return self.draft_export_id > 0

    @rx.var
    def counts(self) -> list[dict[str, str]]:
        return [
            {"label": "Aktivitäten", "value": str(self.activities)},
            {"label": "Stories", "value": str(self.stories)},
            {"label": "Angeboten", "value": str(self.offered)},
            {
                "label": "Kapitel geschrieben",
                "value": f"{self.chapters_written} von {self.chapters_total}",
            },
        ]

    async def _reload(self, offer_id: int) -> None:
        async with get_asyncdb_session() as session:
            overview = await draft_overview.load_overview(session, offer_id)
        self.stages = overview.stages
        self.decisions = overview.decisions
        self.activities = overview.activities
        self.stories = overview.stories
        self.offered = overview.offered
        self.chapters_written = overview.chapters_written
        self.chapters_total = overview.chapters_total
        self.map_revision = overview.map_revision
        self.draft_export_id = overview.draft_export_id
        self.working = overview.working

    @rx.event
    @requires_offer_editor
    async def load_overview(self) -> AsyncGenerator[Any]:
        offer_id = await open_offer_id(self)
        if not offer_id:
            return
        before = self.stages
        try:
            await self._reload(offer_id)
        except Exception:
            logger.exception("Loading the draft overview of offer %s failed", offer_id)
            yield rx.toast.error(LOAD_ERROR, position="top-right")
            return
        if before and self.stages != before:
            # A stage finished: show what it produced on every tab.
            yield REFRESH

    @rx.event
    @requires_offer_editor
    async def confirm_scope(self) -> AsyncGenerator[Any]:
        """Offer every proposed skeleton story; a person decides, never the AI."""
        offer_id = await open_offer_id(self)
        if not offer_id:
            return
        editor = MapEditor(get_asyncdb_session, offer_id, await current_user_name(self))
        try:
            await editor.confirm_skeleton(self.map_revision)
            yield rx.toast.success(SCOPE_CONFIRMED, position="top-right")
        except MapConflictError as exc:
            yield rx.toast.warning(str(exc), position="top-right")
        except MapEditError as exc:
            yield rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Confirming the scope of offer %s failed", offer_id)
            yield rx.toast.error(SCOPE_ERROR, position="top-right")
        await self._reload(offer_id)
        yield MapState.load_map
