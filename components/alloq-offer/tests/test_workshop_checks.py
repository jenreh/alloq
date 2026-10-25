"""Rule checks (pure), commercial values and the findings service."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from alloq_offer.entities import OfferEntity
from alloq_offer.workshop.content.schema import (
    BoundValue,
    CalcContent,
    Paragraph,
    ProseContent,
    Run,
    StoriesContent,
    TableContent,
)
from alloq_offer.workshop.entities import (
    ChapterEntity,
    FindingDecision,
    FindingEntity,
    FindingSeverity,
    FindingSource,
    SourceBlockEntity,
    SourceEntity,
    SourceKind,
    SourceStatus,
    StatementEntity,
    StatementStatus,
    StatementType,
)
from alloq_offer.workshop.services import checks, commercials, findings
from alloq_offer.workshop.services.chapters import ChapterService
from alloq_offer.workshop.services.checks import (
    ChapterFacts,
    CheckInput,
    RuleFinding,
    StatementFacts,
    run_rules,
)
from alloq_offer.workshop.services.findings import FindingError
from alloq_offer.workshop.services.map_edit import MapEditor
from alloq_offer.workshop.services.workspace import open_workspace
from sqlalchemy import select

NOW = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)


def _story(key: str = "US-01", **over) -> dict:
    return {
        "id": 1,
        "key": key,
        "title": "Anfrage ordnen",
        "role": "Disponent",
        "goal": "Anfragen ordnen",
        "benefit": "besser zu planen",
        "archived": False,
        "source_refs": [],
        **over,
    }


def _snapshot(*stories: dict, unassigned: list[dict] | None = None) -> dict:
    return {
        "activities": [
            {
                "archived": False,
                "tasks": [{"archived": False, "stories": list(stories)}],
            }
        ],
        "unassigned": unassigned or [],
    }


def _prose(text: str) -> ProseContent:
    return ProseContent(blocks=[Paragraph(runs=[Run(text=text)])])


def _chapter(key: str = "management_summary", content=None, **over) -> ChapterFacts:
    return ChapterFacts(
        **{
            "key": key,
            "title": "Titel",
            "chapter_type": "prose",
            "required": False,
            "content": content if content is not None else _prose("Text"),
            **over,
        }
    )


def _input(**over) -> CheckInput:
    return CheckInput(
        **{
            "chapters": [],
            "snapshot": _snapshot(_story()),
            "statements": [],
            "days": Decimal(40),
            "risk_days": Decimal(4),
            "cost": Decimal(38000),
            "price": Decimal(52000),
            "price_required": True,
            "commercials_confirmed": True,
            **over,
        }
    )


def _rules(**over) -> set[str]:
    return {f.rule for f in run_rules(_input(**over))}


def test_a_clean_offer_has_no_findings() -> None:
    assert run_rules(_input(chapters=[_chapter()])) == []


def test_empty_required_chapters_block() -> None:
    chapters = [
        _chapter(required=True, content=ProseContent()),
        _chapter("mitwirkung", TableContent(columns=["A"]), required=True),
        _chapter("loesung", ProseContent(), required=False),
    ]
    found = list(run_rules(_input(chapters=chapters)))
    assert [(f.rule, f.severity) for f in found] == [
        ("required_chapter_empty", FindingSeverity.BLOCKER)
    ] * 2


def test_stories_chapter_needs_stories_on_the_map() -> None:
    chapter = _chapter("user_stories", StoriesContent(), chapter_type="stories")
    assert _rules(chapters=[chapter]) == set()
    assert _rules(chapters=[chapter], snapshot=_snapshot()) == {"no_stories"}
    archived = _snapshot(_story(archived=True))
    assert _rules(chapters=[chapter], snapshot=archived) == {"no_stories"}
    assert _rules(chapters=[_chapter()], snapshot=_snapshot()) == set()


def test_story_format_and_placement() -> None:
    bad = _story(goal="Anfragen ordnen\n- Akzeptanzkriterien")
    snapshot = _snapshot(bad, unassigned=[_story("US-09", archived=False)])
    found = {f.rule: f for f in run_rules(_input(snapshot=snapshot))}
    assert found["story_format"].target == "story:US-01"
    assert found["story_unplaced"].severity == FindingSeverity.WARNING
    archived = _snapshot(_story(archived=True), unassigned=[_story(archived=True)])
    assert not run_rules(_input(snapshot=archived))


def test_review_marks_and_placeholders() -> None:
    chapters = [
        _chapter(needs_review=True, review_reason="Map geändert."),
        _chapter("loesung", _prose("Offen: Betriebsmodell klären")),
        _chapter("laufzeit", _prose("Das ist TODO")),
    ]
    found = run_rules(_input(chapters=chapters))
    assert [f.rule for f in found] == [
        "chapter_needs_review",
        "placeholder",
        "placeholder",
    ]
    assert "Map geändert." in found[0].message


def test_statements_conflicts_block_and_requirements_note() -> None:
    items = [
        StatementFacts(1, StatementType.CONFLICT, "Termin A gegen B", False),
        StatementFacts(2, StatementType.CONFLICT, "Gelöst", True),
        StatementFacts(3, StatementType.REQUIREMENT, "Schneller", False),
        StatementFacts(4, StatementType.REQUIREMENT, "Sicher", False),
        StatementFacts(5, StatementType.REQUIREMENT, "Bestätigt", True),
    ]
    found = {f.rule: f for f in run_rules(_input(statements=items))}
    assert found["conflict_open"].target == "statement:1"
    assert found["requirement_open"].message.startswith("2 Anforderungen sind")
    assert found["requirement_open"].severity == FindingSeverity.NOTE
    one = run_rules(_input(statements=items[2:3]))
    assert one[0].message.startswith("1 Anforderung ist")


def test_commercials_rules() -> None:
    calc = _chapter("verguetung", CalcContent(), chapter_type="calc")
    found = run_rules(_input(chapters=[calc], commercials_confirmed=False))
    assert [(f.rule, f.target) for f in found] == [
        ("commercials_unconfirmed", "chapter:verguetung")
    ]
    assert _rules(price=Decimal(0)) == {"commercials_invalid"}
    assert _rules(price=Decimal(100)) == {"commercials_invalid"}
    optional = _input(price_required=False, commercials_confirmed=False, price=0)
    assert run_rules(optional) == []
    assert run_rules(_input(commercials_confirmed=False))[0].target == "workspace"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Wir kalkulieren 40 Personentage.", 0),
        ("Der Preis beträgt 52.000 € netto.", 0),
        ("Zusammen 44 PT.", 0),
        ("Der Preis beträgt 48.000 €.", 1),
        ("Wir brauchen 35 Personentage und 60.000 EUR.", 2),
        ("Version 3 mit 5 Rollen", 0),
        ("Wir planen vierzig Personentage.", 0),
        ("Wir planen fünfunddreißig Personentage.", 1),
        ("Es sind dreiundzwanzig PT", 1),
        ("Der Preis liegt bei 52 k€.", 0),
        ("Der Preis liegt bei 48 T€.", 1),
        ("Zu 0,052 Mio. € angeboten.", 0),
        ("Zu 1,2 Mio. € angeboten.", 1),
        ("30 Tage Zahlungsziel, 12 Manntage Zusatz", 1),
    ],
)
def test_free_numbers_must_match_bound_values(text: str, expected: int) -> None:
    found = run_rules(_input(chapters=[_chapter(content=_prose(text))]))
    assert len([f for f in found if f.rule == "free_number_mismatch"]) == expected
    assert all(f.severity == FindingSeverity.BLOCKER for f in found)


def test_bound_values_are_not_free_numbers() -> None:
    content = ProseContent(blocks=[BoundValue(field="offer.recommended_price")])
    assert not run_rules(_input(chapters=[_chapter(content=content)]))


def test_revoked_sources_flag_stories_and_statements() -> None:
    snapshot = _snapshot(_story(source_refs=[5, 6]), _story("US-02", source_refs=[9]))
    items = [StatementFacts(1, StatementType.FACT, "Beleg", True, [6])]
    found = run_rules(
        _input(snapshot=snapshot, statements=items, revoked_block_ids={6})
    )
    assert [(f.rule, f.target) for f in found] == [
        ("source_revoked", "story:US-01"),
        ("source_revoked", "statement:1"),
    ]
    assert not run_rules(_input(snapshot=snapshot, statements=items))


def test_chapter_target_helper() -> None:
    assert checks.chapter_target("x") == "chapter:x"


# --- commercials -----------------------------------------------------------------


async def _workspace(db) -> ChapterService:
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    service = ChapterService(db.session, 1, "Anna")
    await service.open()
    return service


async def test_confirm_and_view(db) -> None:
    await _workspace(db)
    view = await commercials.load_view(db.session, 1)
    assert not view.confirmed
    assert ("Empfohlener Preis", "2.000 €") in [
        (r["label"], r["value"]) for r in view.rows
    ]
    await commercials.confirm(db.session, 1, "Anna", NOW)
    view = await commercials.load_view(db.session, 1)
    assert (view.confirmed, view.confirmed_by) == (True, "Anna")
    assert view.confirmed_at == "24.10.2026 09:00"


async def test_changed_values_void_the_confirmation_and_flag_chapters(db) -> None:
    service = await _workspace(db)
    await service.save(
        "management_summary",
        1,
        ProseContent(blocks=[BoundValue(field="offer.recommended_price")]),
    )
    await commercials.confirm(db.session, 1, "Anna", NOW)
    async with db.session() as session:
        offer = await session.get(OfferEntity, 1)
        assert offer is not None
        offer.recommended_price = Decimal(3000)
    view = await commercials.load_view(db.session, 1)
    assert not view.confirmed
    async with db.session() as session:
        rows = {
            c.chapter_key: c
            for c in (await session.scalars(select(ChapterEntity))).all()
        }
    assert rows["verguetung"].needs_review
    assert rows["management_summary"].needs_review
    assert not rows["loesung"].needs_review
    assert rows["verguetung"].review_reason == commercials.VOIDED_REASON


async def test_saving_the_offer_voids_the_confirmation_but_not_equal_values(db) -> None:
    service = await _workspace(db)
    await service.save(
        "management_summary",
        1,
        ProseContent(blocks=[BoundValue(field="offer.person_days")]),
    )
    await commercials.confirm(db.session, 1, "Anna", NOW)
    async with db.session() as session:
        offer = await session.get(OfferEntity, 1)
        assert offer is not None
        offer.person_days = Decimal("10")  # same value as 10.00
        assert not await commercials.void_after_offer_edit(session, offer)
    assert (await commercials.load_view(db.session, 1)).confirmed
    async with db.session() as session:
        offer = await session.get(OfferEntity, 1)
        assert offer is not None
        offer.person_days = Decimal("12")
        assert await commercials.void_after_offer_edit(session, offer)
    async with db.session() as session:
        chapter = await session.scalar(
            select(ChapterEntity).where(
                ChapterEntity.chapter_key == "management_summary"
            )
        )
        assert chapter is not None
        assert chapter.needs_review
    assert not await commercials.void_after_offer_edit(
        _NoWorkspaceSession(), OfferEntity(id=99)
    )


class _NoWorkspaceSession:
    """Stands in for a session whose offer has no workspace."""

    async def scalar(self, *_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
        return None


async def test_terms(db) -> None:
    await _workspace(db)
    await commercials.confirm(db.session, 1, "Anna", NOW)
    await commercials.set_price_required(db.session, 1, False)
    assert (await commercials.load_view(db.session, 1)).confirmed
    await commercials.set_validity_date(db.session, 1, date(2026, 12, 31))
    view = await commercials.load_view(db.session, 1)
    assert not view.confirmed
    assert (view.price_required, view.validity_date) == (False, "2026-12-31")


async def test_commercials_need_a_workspace(db) -> None:
    for call in (
        commercials.load_view(db.session, 1),
        commercials.confirm(db.session, 1, "Anna", NOW),
        commercials.set_price_required(db.session, 1, True),
    ):
        with pytest.raises(commercials.CommercialsError):
            await call


async def test_resolved_values_mark_confirmation(db) -> None:
    await _workspace(db)
    async with db.session() as session:
        offer = await session.get(OfferEntity, 1)
        workspace = await open_workspace(session, 1, "")
        assert offer is not None
        before = commercials.resolve_values(offer, workspace)
        assert before["offer.person_days"].text == "10 PT"
        assert before["workspace.validity_date"].text is None
        assert not before["offer.recommended_price"].confirmed
        workspace.validity_date = date(2026, 12, 31)
        assert (
            commercials.resolve_values(offer, workspace)["workspace.validity_date"].text
            == "31.12.2026"
        )


# --- findings --------------------------------------------------------------------


async def _all(db) -> list[FindingEntity]:
    async with db.session() as session:
        return list((await session.scalars(select(FindingEntity))).all())


async def test_run_checks_stores_findings_and_keeps_decisions(db) -> None:
    await _workspace(db)
    async with db.session() as session:
        session.add(
            StatementEntity(
                offer_id=1, type=StatementType.REQUIREMENT, text="Schneller"
            )
        )
    count = await findings.run_checks(db.session, 1)
    assert count >= 3
    rows = await findings.list_findings(db.session, 1)
    assert rows[0]["severity"] == FindingSeverity.BLOCKER
    assert {r["rule"] for r in rows} >= {
        "required_chapter_empty",
        "commercials_unconfirmed",
    }
    note = next(r for r in rows if r["severity"] != FindingSeverity.BLOCKER)
    await findings.decide(
        db.session,
        1,
        note["id"],
        FindingDecision.ACCEPTED,
        reason="Bewusst so",
        user="Anna",
        now=NOW,
    )
    await findings.run_checks(db.session, 1)
    kept = next(
        r for r in await findings.list_findings(db.session, 1) if r["id"] == note["id"]
    )
    assert (kept["decision"], kept["reason"]) == ("akzeptiert", "Bewusst so")
    assert len(await _all(db)) == len(rows)


async def test_blocker_cannot_be_accepted_and_reason_is_needed(db) -> None:
    await _workspace(db)
    await findings.run_checks(db.session, 1)
    rows = await findings.list_findings(db.session, 1)
    blocker = rows[0]
    assert not blocker["acceptable"]
    with pytest.raises(FindingError, match=findings.NOT_ACCEPTABLE):
        await findings.decide(
            db.session,
            1,
            blocker["id"],
            FindingDecision.ACCEPTED,
            reason="egal",
            user="A",
            now=NOW,
        )
    async with db.session() as session:
        session.add(
            FindingEntity(
                offer_id=1,
                fingerprint="x",
                rule="r",
                severity="Hinweis",
                source="Regel",
                target="workspace",
                message="m",
            )
        )
    note = next(
        r for r in await findings.list_findings(db.session, 1) if r["rule"] == "r"
    )
    with pytest.raises(FindingError, match=findings.REASON_NEEDED):
        await findings.decide(
            db.session,
            1,
            note["id"],
            FindingDecision.ACCEPTED,
            reason=" ",
            user="A",
            now=NOW,
        )
    with pytest.raises(FindingError, match=findings.NOT_FOUND):
        await findings.decide(
            db.session,
            1,
            9999,
            FindingDecision.ACCEPTED,
            reason="ok ok",
            user="A",
            now=NOW,
        )
    with pytest.raises(FindingError):
        await findings.decide(
            db.session,
            1,
            note["id"],
            FindingDecision.FIXED,
            reason="",
            user="A",
            now=NOW,
        )


async def test_accepted_finding_can_be_reopened(db) -> None:
    await _workspace(db)
    async with db.session() as session:
        session.add(
            FindingEntity(
                offer_id=1,
                fingerprint="x",
                rule="r",
                severity="Warnung",
                source="Regel",
                target="workspace",
                message="m",
            )
        )
    row = (await findings.list_findings(db.session, 1))[0]
    await findings.decide(
        db.session,
        1,
        row["id"],
        FindingDecision.ACCEPTED,
        reason="weil so",
        user="Anna",
        now=NOW,
    )
    await findings.decide(
        db.session, 1, row["id"], FindingDecision.OPEN, reason="", user="Anna", now=NOW
    )
    again = (await findings.list_findings(db.session, 1))[0]
    assert (again["decision"], again["reason"], again["decided_by"]) == (
        "offen",
        "",
        "",
    )


async def test_solved_problem_is_fixed_and_returns_open(db) -> None:
    service = await _workspace(db)
    await findings.run_checks(db.session, 1)
    await service.save("management_summary", 1, _prose("Ziel, Lösung und Umfang."))
    await findings.run_checks(db.session, 1)
    rules = {r["rule"] for r in await findings.list_findings(db.session, 1)}
    assert "required_chapter_empty" in rules  # other required chapters still empty
    fixed = [
        r
        for r in await _all(db)
        if r.target == "chapter:management_summary"
        and r.rule == "required_chapter_empty"
    ]
    assert fixed[0].decision == FindingDecision.FIXED
    await service.save("management_summary", 2, ProseContent(blocks=[]))
    await findings.run_checks(db.session, 1)
    reopened = [
        r
        for r in await _all(db)
        if r.target == "chapter:management_summary"
        and r.rule == "required_chapter_empty"
    ]
    assert reopened[0].decision == FindingDecision.OPEN


async def test_open_blockers_and_missing_workspace(db) -> None:
    with pytest.raises(FindingError, match=findings.NO_WORKSPACE):
        await findings.run_checks(db.session, 1)
    await _workspace(db)
    await findings.run_checks(db.session, 1)
    async with db.session() as session:
        blockers = await findings.open_blockers(session, 1)
    assert blockers
    assert all(b.severity == FindingSeverity.BLOCKER for b in blockers)


async def test_checks_see_map_statements_and_revoked_sources(db) -> None:
    await _workspace(db)
    editor = MapEditor(db.session, 1, "Anna")
    revision = await editor.add_activity(0, "Bestellen")
    async with db.session() as session:
        source = SourceEntity(
            offer_id=1,
            kind=SourceKind.TEXT,
            title="Mail",
            filename="",
            mime="",
            sha256="a",
            status=SourceStatus.USABLE,
            revoked_at=NOW,
        )
        session.add(source)
        await session.flush()
        block = SourceBlockEntity(
            source_id=source.id, seq=1, anchor={}, kind="text", text="x"
        )
        session.add(block)
        await session.flush()
        session.add(
            StatementEntity(
                offer_id=1,
                type=StatementType.CONFLICT,
                text="A gegen B",
                status=StatementStatus.PROPOSED,
                source_refs=[block.id],
            )
        )
    assert revision == 1
    await findings.run_checks(db.session, 1)
    rules = {r["rule"] for r in await findings.list_findings(db.session, 1)}
    assert {"conflict_open", "source_revoked"} <= rules


def test_ai_findings_are_identified_by_their_text() -> None:
    a = RuleFinding("review", FindingSeverity.WARNING, "workspace", "Rolle fehlt")
    b = RuleFinding("review", FindingSeverity.WARNING, "workspace", "Nutzen fehlt")
    assert findings.fingerprint(FindingSource.AI, a) != findings.fingerprint(
        FindingSource.AI, b
    )
    assert findings.fingerprint(FindingSource.RULE, a) == findings.fingerprint(
        FindingSource.RULE, b
    )
