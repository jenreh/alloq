# ruff: noqa: ARG001
"""Review state and panel."""

from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from alloq_offer.entities import OfferEntity
from alloq_offer.workshop.components import chapters_tab, review_panel
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.entities import FindingEntity, JobEntity, JobStatus
from alloq_offer.workshop.services.chapters import ChapterService
from alloq_offer.workshop.services.workspace import open_workspace
from alloq_offer.workshop.states import review_state
from alloq_offer.workshop.states.review_state import ReviewState
from sqlalchemy import select

from appkit_user.authentication.states import LoginState

MODULE = "alloq_offer.workshop.states.review_state"
CHECK_STATEMENTS = 10


@contextmanager
def _as_editor(state: ReviewState, db, offer_id: int = 1):  # noqa: ANN001, ANN202
    user = MagicMock(is_admin=False, user_id=1, roles=["offer_editor"])
    user.name = "Anna"

    async def _user() -> MagicMock:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value=None)

    async def _get_state(cls: type) -> Any:
        return login if cls is LoginState else SimpleNamespace(offer_id=offer_id)

    registry = MagicMock()
    registry.get.return_value = WorkshopConfig()
    object.__setattr__(state, "get_state", _get_state)
    with (
        patch(f"{MODULE}.get_asyncdb_session", db.session),
        patch(f"{MODULE}.service_registry", return_value=registry),
    ):
        try:
            yield
        finally:
            object.__delattr__(state, "get_state")


async def _run(handler: Any, *args: Any) -> str:
    result = handler(*args)
    if hasattr(result, "__aiter__"):
        return " ".join([str(i) async for i in result if i is not None])
    await result
    return ""


async def _loaded(db) -> ReviewState:  # noqa: ANN001
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    await ChapterService(db.session, 1, "Anna").open()
    state = ReviewState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]
    with _as_editor(state, db):
        await _run(state.run_checks)
    return state


async def test_load_runs_the_checks_and_fills_the_panel(db) -> None:
    state = await _loaded(db)
    assert state.findings
    assert state.blocker_count > 0
    assert "management_summary" in state.blocker_keys
    assert state.calc_rows[0]["label"] == "Personentage"
    assert not state.calc_confirmed
    assert state.price_required
    assert not state.reviewing
    assert state.general_findings == [
        f for f in state.findings if not f["target"].startswith("chapter:")
    ]


async def test_checks_and_panel_load_in_one_session(db) -> None:
    state = await _loaded(db)
    before = state.findings
    with db.round_trips() as trips, _as_editor(state, db):
        await _run(state.run_checks)
    assert state.findings == before
    # Was 4 sessions with 18 statements; the map snapshot now comes from the cache.
    assert trips.sessions == 1
    assert trips.statements <= CHECK_STATEMENTS


async def test_confirm_calculation_voids_blocker_and_records_user(db) -> None:
    state = await _loaded(db)
    before = state.blocker_count
    with _as_editor(state, db):
        await _run(state.confirm_calculation)
    assert state.calc_confirmed
    assert state.calc_confirmed_by == "Anna"
    assert state.blocker_count == before - 1
    async with db.session() as session:
        offer = await session.get(OfferEntity, 1)
        assert offer is not None
        offer.recommended_price = Decimal(9999)
    with _as_editor(state, db):
        await _run(state.run_checks)
    assert not state.calc_confirmed


async def test_terms(db) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.set_price_required, False)
        assert not state.price_required
        await _run(state.set_validity, "2026-12-31")
        assert state.validity_date == "2026-12-31"
        await _run(state.set_validity, "")
        assert state.validity_date == ""
        toast = await _run(state.set_validity, "kein Datum")
    assert "gültiges Datum" in toast


async def test_accept_a_note_needs_a_reason_and_can_be_reopened(db) -> None:
    state = await _loaded(db)
    async with db.session() as session:
        session.add(
            FindingEntity(
                offer_id=1,
                fingerprint="n",
                rule="r",
                severity="Hinweis",
                source="KI",
                target="workspace",
                message="Nur ein Hinweis",
            )
        )
    with _as_editor(state, db):
        await _run(state.run_checks)
        note = next(f for f in state.findings if f["rule"] == "r")
        state.start_decide(note["id"])
        assert (state.deciding_id, state.reason) == (note["id"], "")
        assert "Begründung" in await _run(state.accept_finding)
        state.set_reason("Bewusst so")
        assert await _run(state.accept_finding) == ""
        assert state.deciding_id == 0
        accepted = next(f for f in state.findings if f["rule"] == "r")
        assert (accepted["decision"], accepted["reason"]) == (
            "akzeptiert",
            "Bewusst so",
        )
        await _run(state.reopen_finding, note["id"])
        reopened = next(f for f in state.findings if f["rule"] == "r")
        assert reopened["decision"] == "offen"
        state.start_decide(5)
        state.cancel_decide()
    assert (state.deciding_id, state.reason) == (0, "")


async def test_blockers_cannot_be_accepted(db) -> None:
    state = await _loaded(db)
    blocker = next(f for f in state.findings if f["severity"] == "Blocker")
    state.deciding_id = blocker["id"]
    state.reason = "egal"
    with _as_editor(state, db):
        toast = await _run(state.accept_finding)
    assert "blockierender" in toast


async def test_ai_review_is_queued_once_and_polled(db) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        assert "keine Story Map" in await _run(state.request_ai_review)
    await _make_map(db)
    with _as_editor(state, db):
        assert review_state.REVIEW_QUEUED in await _run(state.request_ai_review)
        assert state.reviewing
        assert await _run(state.request_ai_review) == ""
        assert await _run(state.refresh_review) == ""
        assert state.reviewing
    async with db.session() as session:
        job = (await session.scalars(select(JobEntity))).one()
        job.status = JobStatus.SUCCEEDED
    with _as_editor(state, db):
        await _run(state.refresh_review)
    assert not state.reviewing


async def _make_map(db) -> None:  # noqa: ANN001
    from alloq_offer.workshop.services.map_edit import MapEditor  # noqa: PLC0415

    await MapEditor(db.session, 1, "Anna").add_activity(0, "Bestellen")


async def test_errors_show_a_toast(db) -> None:
    state = await _loaded(db)
    with (
        _as_editor(state, db),
        patch(
            f"{MODULE}.findings.check_offer", AsyncMock(side_effect=RuntimeError("x"))
        ),
    ):
        assert review_state.LOAD_ERROR in await _run(state.run_checks)


def test_components_render_constants() -> None:
    panel = str(review_panel.findings_section())
    assert "request_ai_review" in panel
    assert "run_checks" in panel
    assert "refresh_review" in panel
    assert "confirm_calculation" in str(review_panel.calc_section())
    tab = str(chapters_tab.chapters_tab())
    assert "blocker_keys" in tab
