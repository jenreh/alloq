"""Outline of an offer: add, remove, restore, move, rename and number chapters."""

import pytest
from alloq_offer.entities import OfferEntity
from alloq_offer.workshop.content.schema import Paragraph, ProseContent, Run
from alloq_offer.workshop.entities import ChapterEntity, ChapterRevisionEntity
from alloq_offer.workshop.services import outline
from alloq_offer.workshop.services.chapters import (
    ARCHIVED,
    ChapterError,
    ChapterService,
)
from alloq_offer.workshop.services.draft_overview import load_overview
from alloq_offer.workshop.services.numbering import outline_numbers
from alloq_offer.workshop.services.outline import OutlineService
from alloq_offer.workshop.services.workspace import open_workspace
from alloq_offer.workshop.template_entities import ChapterBlockEntity
from sqlalchemy import delete


async def _outline(db) -> OutlineService:  # noqa: ANN001
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    return OutlineService(db.session, 1, "Anna")


async def _keys(db) -> list[str]:  # noqa: ANN001
    return [c["key"] for c in await ChapterService(db.session, 1, "Anna").open()]


async def _block(db, key: str = "datenschutz", active: bool = True) -> None:  # noqa: ANN001
    async with db.session() as session:
        session.add(
            ChapterBlockEntity(
                key=key,
                title="Datenschutz",
                chapter_type="prose",
                level=2,
                default_content={
                    "chapter_type": "prose",
                    "blocks": [
                        {"type": "paragraph", "runs": [{"text": "Wir schützen."}]}
                    ],
                },
                guiding_question="Wie schützen wir Daten?",
                content_rules=["Keine Zusagen."],
                prompt_text="Nenne die DSGVO.",
                required_info=["Speicherort"],
                checks=[],
                active=active,
            )
        )


def test_numbers_follow_position_and_level() -> None:
    assert outline_numbers([1, 1, 2, 2, 1]) == ["1", "2", "2.1", "2.2", "3"]
    assert outline_numbers([2, 1, 2]) == ["1.1", "2", "2.1"]
    assert outline_numbers([]) == []


async def test_add_library_block_after_a_chapter(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    await _block(db)
    library = await service.library()
    assert [b["key"] for b in library] == ["datenschutz"]
    key = await service.add_chapter("management_summary", block_key="datenschutz")
    assert key.startswith(outline.NEW_KEY_PREFIX)
    assert len(key) == len(outline.NEW_KEY_PREFIX) + 8
    keys = await _keys(db)
    assert keys[:2] == ["management_summary", key]
    views = await ChapterService(db.session, 1, "Anna").open()
    added = views[1]
    assert (added["title"], added["level"], added["required"]) == (
        "Datenschutz",
        2,
        False,
    )
    assert added["guiding_question"] == "Wie schützen wir Daten?"
    loaded = await ChapterService(db.session, 1, "Anna").load(key)
    assert loaded["content"]["blocks"][0]["runs"][0]["text"] == "Wir schützen."
    assert loaded["revision"] == 1
    assert await service.library() == []


async def test_add_blank_chapter_of_each_type(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    before = len(await _keys(db))
    for chapter_type in ("prose", "table", "stories", "calc"):
        key = await service.add_chapter(
            None, chapter_type=chapter_type, title=f"Neu {chapter_type}"
        )
        loaded = await ChapterService(db.session, 1, "Anna").load(key)
        assert loaded["content"]["chapter_type"] == chapter_type
    keys = await _keys(db)
    assert len(keys) == before + 4
    with pytest.raises(ChapterError, match=outline.TITLE_NEEDED):
        await service.add_chapter(None, chapter_type="prose", title="  ")
    with pytest.raises(ChapterError, match=outline.UNKNOWN_TYPE):
        await service.add_chapter(None, chapter_type="bild", title="Bild")


async def test_add_refuses_unknown_inactive_or_used_block(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    await _block(db, "alt", active=False)
    with pytest.raises(ChapterError, match=outline.NO_BLOCK):
        await service.add_chapter(None, block_key="alt")
    with pytest.raises(ChapterError, match=outline.NO_BLOCK):
        await service.add_chapter(None, block_key="gibt_es_nicht")
    with pytest.raises(ChapterError, match=outline.BLOCK_IN_USE):
        await service.add_chapter(None, block_key="laufzeit")
    with pytest.raises(ChapterError, match="Kapitel gibt es nicht"):
        await service.add_chapter("gibt_es_nicht", chapter_type="prose", title="X")


async def test_required_chapters_cannot_be_removed(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    with pytest.raises(ChapterError, match=outline.REQUIRED):
        await service.remove_chapter("management_summary")


async def test_remove_and_restore_keep_revisions(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    chapters = ChapterService(db.session, 1, "Anna")
    text = ProseContent(blocks=[Paragraph(runs=[Run(text="Annahme")])])
    await chapters.save("annahmen_risiken", 1, text)
    await service.remove_chapter("annahmen_risiken")
    assert "annahmen_risiken" not in await _keys(db)
    assert await service.removed() == [
        {"key": "annahmen_risiken", "title": "Annahmen und Risiken"}
    ]
    with pytest.raises(ChapterError, match="Kapitel gibt es nicht"):
        await chapters.load("annahmen_risiken")
    await service.restore_chapter("annahmen_risiken")
    assert (await _keys(db))[-1] == "annahmen_risiken"
    assert await service.removed() == []
    loaded = await chapters.load("annahmen_risiken")
    assert (loaded["revision"], loaded["content"]["blocks"][0]["runs"][0]["text"]) == (
        2,
        "Annahme",
    )
    with pytest.raises(ChapterError, match="Kapitel gibt es nicht"):
        await service.restore_chapter("annahmen_risiken")
    views = await ChapterService(db.session, 1, "Anna").open()
    assert [v["position"] for v in views] == list(range(len(views)))
    restored = views[-1]
    assert (restored["needs_review"], restored["review_reason"]) == (
        True,
        outline.RESTORED,
    )


async def test_move_keeps_positions_dense(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    before = await _keys(db)
    await service.move_chapter("verguetung", 0)
    after = await _keys(db)
    assert after[0] == "verguetung"
    assert sorted(after) == sorted(before)
    await service.move_chapter("verguetung", 99)
    assert (await _keys(db))[-1] == "verguetung"
    await service.remove_chapter("leistungen")
    views = await ChapterService(db.session, 1, "Anna").open()
    assert [v["position"] for v in views] == list(range(len(views)))
    assert views[0]["number"] == "1"


async def test_rename_and_level(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    await service.rename_chapter("loesung", "  Unsere Lösung  ")
    await service.set_level("loesung", 1)
    views = {v["key"]: v for v in await ChapterService(db.session, 1, "Anna").open()}
    assert (views["loesung"]["title"], views["loesung"]["level"]) == (
        "Unsere Lösung",
        1,
    )
    with pytest.raises(ChapterError, match=outline.TITLE_NEEDED):
        await service.rename_chapter("loesung", "")
    with pytest.raises(ChapterError, match=outline.BAD_LEVEL):
        await service.set_level("loesung", 3)


async def test_protected_chapters_and_archived_offers_are_locked(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    await ChapterService(db.session, 1, "Anna").set_protected("leistungen", True)
    with pytest.raises(ChapterError, match="geschützt"):
        await service.remove_chapter("leistungen")
    with pytest.raises(ChapterError, match="geschützt"):
        await service.rename_chapter("leistungen", "Neu")
    async with db.session() as session:
        offer = await session.get(OfferEntity, 1)
        assert offer is not None
        offer.archived = True
    with pytest.raises(ChapterError, match=ARCHIVED):
        await service.move_chapter("laufzeit", 0)
    with pytest.raises(ChapterError, match=ARCHIVED):
        await service.add_chapter(None, chapter_type="prose", title="X")


async def test_a_block_is_used_once_even_after_removal(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    await _block(db)
    key = await service.add_chapter(None, block_key="datenschutz", title="  ")
    views = {v["key"]: v for v in await ChapterService(db.session, 1, "Anna").open()}
    assert views[key]["title"] == "Datenschutz"
    await service.remove_chapter(key)
    assert await service.library() == []
    with pytest.raises(ChapterError, match=outline.BLOCK_IN_USE):
        await service.add_chapter(None, block_key="datenschutz")
    await service.restore_chapter(key)
    assert (await _keys(db))[-1] == key


async def test_an_invalid_block_is_refused_in_german(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    async with db.session() as session:
        session.add(
            ChapterBlockEntity(
                key="kaputt",
                title="Kaputt",
                chapter_type="table",
                level=3,
                default_content={"chapter_type": "table", "columns": ["A"]},
            )
        )
    with pytest.raises(ChapterError, match=outline.NO_BLOCK):
        await service.add_chapter(None, block_key="kaputt")


async def test_titles_are_one_short_line(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    for title in ("Zeile\nzwei", "x" * 256):
        with pytest.raises(ChapterError, match="Überschrift"):
            await service.rename_chapter("loesung", title)


async def test_first_chapter_stays_level_one(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    with pytest.raises(ChapterError, match=outline.FIRST_LEVEL):
        await service.set_level("management_summary", 2)
    await service.move_chapter("loesung", 0)
    views = await ChapterService(db.session, 1, "Anna").open()
    assert (views[0]["key"], views[0]["level"], views[0]["number"]) == (
        "loesung",
        1,
        "1",
    )


async def test_outline_has_a_chapter_limit(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    count = len(await _keys(db))
    for _ in range(outline.MAX_CHAPTERS - count):
        await service.add_chapter(None, chapter_type="prose", title="Mehr")
    with pytest.raises(ChapterError, match=outline.TOO_MANY):
        await service.add_chapter(None, chapter_type="prose", title="Zu viel")


async def test_adding_to_an_older_offer_creates_its_template_chapters(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    async with db.session() as session:
        await session.execute(delete(ChapterRevisionEntity))
        await session.execute(delete(ChapterEntity))
    key = await service.add_chapter(None, chapter_type="prose", title="Neu")
    keys = await _keys(db)
    assert keys[0] == "management_summary"
    assert keys[-1] == key


async def test_protected_or_archived_chapters_do_not_move(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    await ChapterService(db.session, 1, "Anna").set_protected("laufzeit", True)
    with pytest.raises(ChapterError, match="geschützt"):
        await service.move_chapter("laufzeit", 0)
    with pytest.raises(ChapterError, match="geschützt"):
        await service.set_level("laufzeit", 2)
    await service.remove_chapter("leistungen")
    async with db.session() as session:
        offer = await session.get(OfferEntity, 1)
        assert offer is not None
        offer.archived = True
    with pytest.raises(ChapterError, match=ARCHIVED):
        await service.restore_chapter("leistungen")
    with pytest.raises(ChapterError, match=ARCHIVED):
        await ChapterService(db.session, 1, "Anna").save(
            "loesung", 1, ProseContent(blocks=[])
        )


async def test_overview_counts_only_the_outline(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    async with db.session() as session:
        before = (await load_overview(session, 1)).chapters_total
    await service.remove_chapter("leistungen")
    async with db.session() as session:
        assert (await load_overview(session, 1)).chapters_total == before - 1


async def test_a_blank_chapter_takes_the_level_it_follows(db) -> None:  # noqa: ANN001
    service = await _outline(db)
    sub = await service.add_chapter("loesung", chapter_type="prose", title="Detail")
    main = await service.add_chapter("laufzeit", chapter_type="prose", title="Neu")
    last = await service.add_chapter(None, chapter_type="prose", title="Ende")
    views = {v["key"]: v for v in await ChapterService(db.session, 1, "Anna").open()}
    assert (views[sub]["level"], views[main]["level"], views[last]["level"]) == (
        2,
        1,
        1,
    )
