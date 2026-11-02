"""State of the review in the chapters tab: findings, checks and the calculation."""

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from typing import Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.entities import (
    FindingDecision,
    FindingSeverity,
    JobStatus,
)
from alloq_offer.workshop.repositories import job_repo
from alloq_offer.workshop.services import commercials, findings
from alloq_offer.workshop.services.review_request import (
    REVIEW_JOB,
    ReviewNotPossibleError,
    request_review,
)
from alloq_offer.workshop.services.review_view import load_review
from alloq_offer.workshop.states.helpers import current_user_name, open_offer_id
from appkit_commons.database.session import get_asyncdb_session
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)

LOAD_ERROR = "Die Prüfung konnte nicht geladen werden."
SAVE_ERROR = "Die Änderung konnte nicht gespeichert werden."
REVIEW_QUEUED = "Die KI prüft das Angebot."
REVIEW_ERROR = "Die Prüfung konnte nicht angefordert werden."
CHAPTER_PREFIX = "chapter:"
WORKING = (JobStatus.QUEUED, JobStatus.RUNNING)


class ReviewState(rx.State):
    """Findings of the open offer and its calculation."""

    findings: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    calc_rows: rx.Field[list[dict[str, str]]] = rx.field(default_factory=list)
    calc_confirmed: rx.Field[bool] = rx.field(False)
    calc_confirmed_by: rx.Field[str] = rx.field("")
    calc_confirmed_at: rx.Field[str] = rx.field("")
    price_required: rx.Field[bool] = rx.field(True)
    validity_date: rx.Field[str] = rx.field("")
    deciding_id: rx.Field[int] = rx.field(0)
    reason: rx.Field[str] = rx.field("")
    review_job: rx.Field[str] = rx.field("")

    @rx.var
    def blocker_keys(self) -> list[str]:
        return _chapter_keys(self.findings, blockers=True)

    @rx.var
    def other_keys(self) -> list[str]:
        return _chapter_keys(self.findings, blockers=False)

    @rx.var
    def general_findings(self) -> list[dict[str, Any]]:
        return [f for f in self.findings if not f["target"].startswith(CHAPTER_PREFIX)]

    @rx.var
    def blocker_count(self) -> int:
        return sum(
            1
            for f in self.findings
            if f["severity"] == FindingSeverity.BLOCKER
            and f["decision"] == FindingDecision.OPEN
        )

    @rx.var
    def reviewing(self) -> bool:
        return self.review_job in WORKING

    async def _reload(self, offer_id: int, *, check: bool = False) -> None:
        loaded = await load_review(get_asyncdb_session, offer_id, check=check)
        self.findings = loaded.findings
        view = loaded.commercials
        self.calc_rows = view.rows
        self.calc_confirmed = view.confirmed
        self.calc_confirmed_by = view.confirmed_by
        self.calc_confirmed_at = view.confirmed_at
        self.price_required = view.price_required
        self.validity_date = view.validity_date
        self.review_job = loaded.review_job

    async def _guarded(
        self, action: Any, error: str, *, check: bool = False
    ) -> Any | None:
        """Run a service call and reload; a toast comes back on failure.

        ``check`` runs the rule checks in the reload, after the call.
        """
        offer_id = await open_offer_id(self)
        if not offer_id:
            return None
        try:
            if action is not None:
                await action(offer_id)
            await self._reload(offer_id, check=check)
        except (findings.FindingError, commercials.CommercialsError) as exc:
            return rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Review action for offer %s failed", offer_id)
            return rx.toast.error(error, position="top-right")
        return None

    @rx.event
    @requires_offer_editor
    async def run_checks(self) -> AsyncGenerator[Any]:
        """Run the rule checks and load findings; also runs when the tab opens."""
        toast = await self._guarded(None, LOAD_ERROR, check=True)
        if toast:
            yield toast

    @rx.event
    @requires_offer_editor
    async def request_ai_review(self) -> AsyncGenerator[Any]:
        offer_id = await open_offer_id(self)
        if not offer_id or self.reviewing:
            return
        config = service_registry().get(WorkshopConfig)
        try:
            await request_review(
                get_asyncdb_session,
                offer_id,
                now=datetime.now(UTC),
                max_attempts=config.max_attempts,
            )
            self.review_job = JobStatus.QUEUED
            yield rx.toast.info(REVIEW_QUEUED, position="top-right")
        except ReviewNotPossibleError as exc:
            yield rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Queueing the review of offer %s failed", offer_id)
            yield rx.toast.error(REVIEW_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def refresh_review(self) -> AsyncGenerator[Any]:
        """Poll while the AI works; reloads once when the job has finished."""
        offer_id = await open_offer_id(self)
        if not offer_id:
            return
        async with get_asyncdb_session() as session:
            job = await job_repo.find_latest(session, offer_id, REVIEW_JOB)
        status = job.status if job is not None else ""
        if status in WORKING:
            return
        was_working = self.reviewing
        self.review_job = status
        if was_working:
            try:
                await self._reload(offer_id)
            except Exception:
                logger.exception("Reloading findings of offer %s failed", offer_id)
                yield rx.toast.error(LOAD_ERROR, position="top-right")

    @rx.event
    def start_decide(self, finding_id: int) -> None:
        self.deciding_id = finding_id
        self.reason = ""

    @rx.event
    def cancel_decide(self) -> None:
        self.deciding_id = 0
        self.reason = ""

    @rx.event
    def set_reason(self, value: str) -> None:
        self.reason = value

    @rx.event
    @requires_offer_editor
    async def accept_finding(self) -> AsyncGenerator[Any]:
        finding_id, reason = self.deciding_id, self.reason
        user = await current_user_name(self)
        toast = await self._guarded(
            lambda offer_id: findings.decide(
                get_asyncdb_session,
                offer_id,
                finding_id,
                FindingDecision.ACCEPTED,
                reason=reason,
                user=user,
                now=datetime.now(UTC),
            ),
            SAVE_ERROR,
        )
        if toast:
            yield toast
        else:
            self.deciding_id = 0
            self.reason = ""

    @rx.event
    @requires_offer_editor
    async def reopen_finding(self, finding_id: int) -> AsyncGenerator[Any]:
        toast = await self._guarded(
            lambda offer_id: findings.decide(
                get_asyncdb_session,
                offer_id,
                finding_id,
                FindingDecision.OPEN,
                reason="",
                user="",
                now=datetime.now(UTC),
            ),
            SAVE_ERROR,
        )
        if toast:
            yield toast

    @rx.event
    @requires_offer_editor
    async def confirm_calculation(self) -> AsyncGenerator[Any]:
        user = await current_user_name(self)
        toast = await self._guarded(
            lambda offer_id: commercials.confirm(
                get_asyncdb_session, offer_id, user, datetime.now(UTC)
            ),
            SAVE_ERROR,
            check=True,
        )
        if toast:
            yield toast

    @rx.event
    @requires_offer_editor
    async def set_price_required(self, value: bool) -> AsyncGenerator[Any]:
        toast = await self._guarded(
            lambda offer_id: commercials.set_price_required(
                get_asyncdb_session, offer_id, value
            ),
            SAVE_ERROR,
            check=True,
        )
        if toast:
            yield toast

    @rx.event
    @requires_offer_editor
    async def set_validity(self, value: str) -> AsyncGenerator[Any]:
        try:
            parsed = date.fromisoformat(value) if value else None
        except ValueError:
            yield rx.toast.error("Bitte geben Sie ein gültiges Datum ein.")
            return
        toast = await self._guarded(
            lambda offer_id: commercials.set_validity_date(
                get_asyncdb_session, offer_id, parsed
            ),
            SAVE_ERROR,
            check=True,
        )
        if toast:
            yield toast


def _chapter_keys(rows: list[dict[str, Any]], *, blockers: bool) -> list[str]:
    """Chapters with an open finding of the blocker class, or of the lighter ones."""
    return sorted(
        {
            row["target"].removeprefix(CHAPTER_PREFIX)
            for row in rows
            if row["target"].startswith(CHAPTER_PREFIX)
            and row["decision"] == FindingDecision.OPEN
            and (row["severity"] == FindingSeverity.BLOCKER) == blockers
        }
    )
