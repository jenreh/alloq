"""A stand-in for the language model that drafts from sentences of the sources.

Used with ``ai_provider: demo`` where no Azure OpenAI deployment exists, so the
whole workshop flow runs locally. It invents nothing: stories, statements and
chapter text quote sentences of the sources and cite their blocks.
"""

import re
from dataclasses import dataclass
from pathlib import PurePath

from alloq_offer.workshop.ai.port import (
    ChapterRequest,
    MapRequest,
    ReviewRequest,
    SourceText,
)
from alloq_offer.workshop.ai.schemas import (
    ProposedActivity,
    ProposedBriefing,
    ProposedChapter,
    ProposedMap,
    ProposedPoint,
    ProposedReview,
    ProposedStatement,
    ProposedStory,
    ProposedTask,
    ReviewRemark,
)
from alloq_offer.workshop.content.schema import BulletList, Paragraph, Run
from alloq_offer.workshop.entities import StatementType
from alloq_offer.workshop.services.story_rules import story_problems

DEMO_MODEL = "demo-extraktiv"
DEMO_PROMPT = "demo_v1"
DEFAULT_ROLE = "Anwender"
TASK_TITLE = "Anforderungen"
SLICES = ("Erste Ausbaustufe", "Spätere Ausbaustufe")
MAX_STORIES_PER_SOURCE = 4
MAX_STATEMENTS = 24
MAX_CHAPTER_ITEMS = 6
MIN_SENTENCE = 15
MAX_SENTENCE = 280
TITLE_WORDS = 6
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
REQUIREMENT = re.compile(
    r"^(?:(?:die|der|das|unsere|alle)\s+)?"
    r"(?P<role>[A-ZÄÖÜ][\wÄÖÜäöüß-]*(?:\s+[\wÄÖÜäöüß-]+){0,2})\s+"
    r"(?:soll|sollen|möchte|möchten|muss|müssen|will|wollen)\s+"
    r"(?P<goal>.+?)[.!]?$",
    re.IGNORECASE,
)
MAIL_HEADER = re.compile(r"^\s*(betreff|von|an|cc|datum|gesendet):", re.I)
ASSUMPTION = re.compile(r"^(annahme|wir gehen davon aus|voraussichtlich)", re.I)
CHAPTER_INTRO = "Aus den Quellen ergibt sich zu „{title}“:"
EMPTY_CHAPTER = "Die Quellen enthalten zu „{title}“ noch keine Aussagen."
REVIEW_EMPTY = "Das Kapitel ist noch leer."


@dataclass(frozen=True)
class _Sentence:
    text: str
    block_id: int
    source: SourceText


def _sentences(source: SourceText) -> list[_Sentence]:
    """Sentences per line: PDF lines and mail headers are no running text."""
    return [
        _Sentence(part, block.id, source)
        for block in source.blocks
        for line in block.text.splitlines()
        if not MAIL_HEADER.match(line)
        for part in SENTENCE_END.split(" ".join(line.split()))
        if MIN_SENTENCE <= len(part) <= MAX_SENTENCE
    ]


def _source_name(source: SourceText) -> str:
    return PurePath(source.title).stem or source.title


def _title(goal: str) -> str:
    words = goal.split()[:TITLE_WORDS]
    text = " ".join(words).rstrip(",;:")
    return text[:1].upper() + text[1:]


def _story(sentence: _Sentence) -> ProposedStory | None:
    match = REQUIREMENT.match(sentence.text)
    if match is None:
        return None
    role, goal = match["role"], match["goal"]
    benefit = f"die Anforderung aus „{_source_name(sentence.source)}“ zu erfüllen"
    title = _title(goal)
    if story_problems(title, role, goal, benefit):
        return None
    return ProposedStory(
        title=title,
        role=role,
        goal=goal,
        benefit=benefit,
        origin="Kunde",
        source_refs=[sentence.block_id],
    )


def _fallback_story(source: SourceText) -> ProposedStory:
    name = _source_name(source)
    return ProposedStory(
        title=f"Inhalte aus {name} nutzen"[:120],
        role=DEFAULT_ROLE,
        goal=f"die Inhalte aus „{name}“ im System nutzen",
        benefit="die Anforderungen der Quelle abzudecken",
        source_refs=[source.blocks[0].id] if source.blocks else [],
    )


def _statement_type(text: str) -> StatementType:
    if text.endswith("?"):
        return StatementType.OPEN_POINT
    if ASSUMPTION.match(text):
        return StatementType.ASSUMPTION
    if REQUIREMENT.match(text):
        return StatementType.REQUIREMENT
    return StatementType.FACT


def _runs(text: str) -> list[Run]:
    return [Run(text=text)]


def _wanted_types(title: str) -> tuple[str, ...]:
    lowered = title.lower()
    if "annahme" in lowered or "risik" in lowered:
        return (StatementType.ASSUMPTION, StatementType.OPEN_POINT)
    if "rahmen" in lowered or "abwicklung" in lowered or "laufzeit" in lowered:
        return (StatementType.FACT, StatementType.ASSUMPTION)
    return (StatementType.REQUIREMENT, StatementType.FACT)


class DemoOfferAi:
    """Implements every AI port by quoting the sources; no network, no model."""

    model_name = DEMO_MODEL
    map_prompt_version = DEMO_PROMPT
    briefing_prompt_version = DEMO_PROMPT
    chapter_prompt_version = DEMO_PROMPT
    review_prompt_version = DEMO_PROMPT
    map_additions_prompt_version = DEMO_PROMPT

    async def propose_map(self, sources: list[SourceText]) -> ProposedMap:
        activities: list[ProposedActivity] = []
        for source in sources:
            stories = [
                story
                for sentence in _sentences(source)
                if (story := _story(sentence)) is not None
            ][:MAX_STORIES_PER_SOURCE] or [_fallback_story(source)]
            for position, story in enumerate(stories):
                story.skeleton = position == 0
                story.slice = SLICES[0] if position == 0 else SLICES[1]
            activities.append(
                ProposedActivity(
                    title=_source_name(source)[:120],
                    tasks=[ProposedTask(title=TASK_TITLE, stories=stories)],
                )
            )
        names = ", ".join(_source_name(source) for source in sources)
        return ProposedMap(
            vision=f"Angebot auf Grundlage von: {names}"[:500],
            roles=sorted(
                {
                    story.role
                    for activity in activities
                    for task in activity.tasks
                    for story in task.stories
                }
            ),
            activities=activities,
            slices=list(SLICES),
            open_questions=[
                ProposedPoint(text=f"In „{_source_name(source)}“ fehlt: {gap}")
                for source in sources
                for gap in source.gaps
            ],
        )

    async def propose_briefing(self, sources: list[SourceText]) -> ProposedBriefing:
        statements = [
            ProposedStatement(
                type=_statement_type(sentence.text),
                text=sentence.text,
                source_refs=[sentence.block_id],
            )
            for source in sources
            for sentence in _sentences(source)
        ]
        return ProposedBriefing(statements=statements[:MAX_STATEMENTS])

    async def propose_chapter(self, request: ChapterRequest) -> ProposedChapter:
        wanted = _wanted_types(request.title)
        items = [
            text
            for line in request.statements
            for kind, _, text in [line.partition(": ")]
            if kind in wanted
        ][:MAX_CHAPTER_ITEMS]
        if not items:
            note = EMPTY_CHAPTER.format(title=request.title)
            return ProposedChapter(blocks=[Paragraph(runs=_runs(note))])
        intro = CHAPTER_INTRO.format(title=request.title)
        return ProposedChapter(
            blocks=[
                Paragraph(runs=_runs(intro)),
                BulletList(items=[_runs(item) for item in items]),
            ]
        )

    async def propose_review(self, request: ReviewRequest) -> ProposedReview:
        return ProposedReview(
            findings=[
                ReviewRemark(
                    target=f"chapter:{chapter.key}",
                    message=REVIEW_EMPTY,
                    severity="Warnung",
                )
                for chapter in request.chapters
                if len(chapter.lines) < 2  # noqa: PLR2004  # intro plus one point
            ]
        )

    async def propose_map_additions(self, request: MapRequest) -> ProposedMap:
        proposed = await self.propose_map(request.sources)
        for activity in proposed.activities:
            for task in activity.tasks:
                task.stories = [
                    s for s in task.stories if s.goal not in request.map_outline
                ]
        proposed.activities = [
            a for a in proposed.activities if any(t.stories for t in a.tasks)
        ]
        proposed.open_questions = []
        return proposed
