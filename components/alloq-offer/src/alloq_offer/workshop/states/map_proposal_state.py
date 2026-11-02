"""State of the AI proposals for the map: ask, compare, take over (spec 10.1)."""

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.entities import JobStatus
from alloq_offer.workshop.repositories import job_repo
from alloq_offer.workshop.services import map_proposals
from alloq_offer.workshop.states.helpers import current_user_name, open_offer_id
from alloq_offer.workshop.states.map_state import MapState
from appkit_commons.database.session import get_asyncdb_session
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)

LOAD_ERROR = "Der Vorschlag konnte nicht geladen werden."
REQUEST_ERROR = "Der Vorschlag konnte nicht angefordert werden."
QUEUED = "Die KI bereitet einen Vorschlag für die Map vor."
TAKEN_OVER = "Der Vorschlag wurde in die Map übernommen."
NO_SELECTION = "Bitte wählen Sie zuerst eine Story."
WORKING = (JobStatus.QUEUED, JobStatus.RUNNING)


class MapProposalState(rx.State):
    """The newest AI proposal for the map of the open offer."""

    proposal: rx.Field[dict[str, Any]] = rx.field(default_factory=dict)
    instruction: rx.Field[str] = rx.field("")
    job: rx.Field[str] = rx.field("")

    @rx.var
    def has_proposal(self) -> bool:
        return bool(self.proposal)

    @rx.var
    def working(self) -> bool:
        return self.job in WORKING

    @rx.var
    def is_stale(self) -> bool:
        return bool(self.proposal.get("stale", False))

    async def _reload(self, offer_id: int) -> None:
        found = await map_proposals.open_proposal(get_asyncdb_session, offer_id)
        self.proposal = found or {}
        async with get_asyncdb_session() as session:
            job = await job_repo.find_latest(
                session, offer_id, map_proposals.MAP_PROPOSAL_JOB
            )
        self.job = job.status if job is not None else ""

    @rx.event
    def set_instruction(self, value: str) -> None:
        self.instruction = value

    @rx.event
    @requires_offer_editor
    async def load_proposal(self) -> AsyncGenerator[Any]:
        offer_id = await open_offer_id(self)
        if not offer_id:
            return
        try:
            await self._reload(offer_id)
        except Exception:
            logger.exception("Loading the map proposal of offer %s failed", offer_id)
            yield rx.toast.error(LOAD_ERROR, position="top-right")

    async def _request(self, instruction: str) -> AsyncGenerator[Any]:
        offer_id = await open_offer_id(self)
        if not offer_id or self.working:
            return
        config = service_registry().get(WorkshopConfig)
        try:
            await map_proposals.request_map_proposal(
                get_asyncdb_session,
                offer_id,
                instruction,
                now=datetime.now(UTC),
                max_attempts=config.max_attempts,
            )
            self.job = JobStatus.QUEUED
            yield rx.toast.info(QUEUED, position="top-right")
        except map_proposals.MapProposalError as exc:
            yield rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Queueing the map proposal of offer %s failed", offer_id)
            yield rx.toast.error(REQUEST_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def propose_steps(self) -> AsyncGenerator[Any]:
        """Ask for missing process steps, or for what the free text says."""
        async for event in self._request(self.instruction):
            yield event

    @rx.event
    @requires_offer_editor
    async def propose_split(self) -> AsyncGenerator[Any]:
        """Ask the AI to split the selected story into smaller ones."""
        selected = (await self.get_state(MapState)).selected
        if not selected:
            yield rx.toast.error(NO_SELECTION, position="top-right")
            return
        text = map_proposals.SPLIT_INSTRUCTION.format(
            key=selected["key"], title=selected["title"]
        )
        async for event in self._request(text):
            yield event

    @rx.event
    @requires_offer_editor
    async def refresh_proposal(self) -> AsyncGenerator[Any]:
        """Poll while the AI works; reloads once when the job has finished."""
        offer_id = await open_offer_id(self)
        if not offer_id:
            return
        async with get_asyncdb_session() as session:
            job = await job_repo.find_latest(
                session, offer_id, map_proposals.MAP_PROPOSAL_JOB
            )
        status = job.status if job is not None else ""
        if status in WORKING:
            return
        was_working = self.working
        self.job = status
        if was_working:
            try:
                await self._reload(offer_id)
            except Exception:
                logger.exception("Reloading map proposal of offer %s failed", offer_id)
                yield rx.toast.error(LOAD_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def accept_proposal(self) -> AsyncGenerator[Any]:
        offer_id = await open_offer_id(self)
        if not offer_id or not self.proposal:
            return
        try:
            await map_proposals.accept(
                get_asyncdb_session,
                offer_id,
                int(self.proposal["id"]),
                await current_user_name(self),
            )
            yield rx.toast.success(TAKEN_OVER, position="top-right")
        except map_proposals.MapProposalError as exc:
            yield rx.toast.warning(str(exc), position="top-right")
        except Exception:
            logger.exception("Taking over map proposal of offer %s failed", offer_id)
            yield rx.toast.error(REQUEST_ERROR, position="top-right")
            return
        await self._reload(offer_id)
        yield MapState.load_map

    @rx.event
    @requires_offer_editor
    async def reject_proposal(self) -> AsyncGenerator[Any]:
        offer_id = await open_offer_id(self)
        if not offer_id or not self.proposal:
            return
        try:
            await map_proposals.reject(
                get_asyncdb_session, offer_id, int(self.proposal["id"])
            )
            await self._reload(offer_id)
        except map_proposals.MapProposalError as exc:
            yield rx.toast.warning(str(exc), position="top-right")
        except Exception:
            logger.exception("Rejecting map proposal of offer %s failed", offer_id)
            yield rx.toast.error(REQUEST_ERROR, position="top-right")
