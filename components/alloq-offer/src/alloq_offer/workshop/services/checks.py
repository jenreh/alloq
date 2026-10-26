"""Rule checks of the offer (spec 11.1): pure functions over a snapshot of the offer.

Each rule returns findings; none changes content. Blockers keep the final output
closed, warnings and notes can be accepted with a reason.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from alloq_offer.workshop.content.schema import (
    ProseContent,
    StoriesContent,
    TableContent,
)
from alloq_offer.workshop.content.text import Content, content_lines
from alloq_offer.workshop.entities import FindingSeverity, StatementType
from alloq_offer.workshop.services.story_rules import (
    CRITERIA_PATTERNS,
    story_problems,
)

BLOCKER = FindingSeverity.BLOCKER
WARNING = FindingSeverity.WARNING
NOTE = FindingSeverity.NOTE

PLACEHOLDER = re.compile(
    r"\b(TODO|TBD|XXX|Lorem ipsum)\b|\[\s*(…|\.\.\.)?\s*\]|^\s*Offen:",
    re.IGNORECASE | re.MULTILINE,
)
ONES = (
    "null eins zwei drei vier fünf sechs sieben acht neun zehn elf zwölf "
    "dreizehn vierzehn fünfzehn sechzehn siebzehn achtzehn neunzehn"
)
TENS_WORDS = "zwanzig dreißig vierzig fünfzig sechzig siebzig achtzig neunzig"
NUMBER_WORDS = {word: value for value, word in enumerate(ONES.split())}
TENS = {word: value * 10 for value, word in enumerate(TENS_WORDS.split(), 2)}
UNITS = r"(PT\b|Personentage?n?\b|Manntage?n?\b|€|EUR\b|Euro\b)"
AMOUNT = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?\s*(Mio\.?|k|T)?\s*" + UNITS,
    re.IGNORECASE,
)
WORD_AMOUNT = re.compile(
    r"\b(?:(ein|zwei|drei|vier|fünf|sechs|sieben|acht|neun)und)?"
    r"(" + "|".join([*NUMBER_WORDS, *TENS]) + r")\s+" + UNITS,
    re.IGNORECASE,
)
SCALES = {"mio": Decimal(1_000_000), "mio.": Decimal(1_000_000), "k": Decimal(1000)}
DAY_UNITS = ("pt", "personentag", "manntag")
CONTAINS_ALL_STORIES = "contains_all_stories"
NO_ACCEPTANCE_CRITERIA = "no_acceptance_criteria"
COMMERCIALS_CONFIRMED = "commercials_confirmed"
# Checks a chapter can bring along; the findings are reported on that chapter.
CHAPTER_CHECKS: dict[str, str] = {
    CONTAINS_ALL_STORIES: "Enthält alle Stories der Map",
    NO_ACCEPTANCE_CRITERIA: "Keine Akzeptanzkriterien",
    COMMERCIALS_CONFIRMED: "Kalkulation bestätigt",
}


@dataclass(frozen=True)
class RuleFinding:
    rule: str
    severity: FindingSeverity
    target: str
    message: str
    key: str = ""


@dataclass(frozen=True)
class ChapterFacts:
    key: str
    title: str
    chapter_type: str
    required: bool
    content: Content
    needs_review: bool = False
    review_reason: str = ""
    checks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StatementFacts:
    id: int
    type: str
    text: str
    confirmed: bool
    source_refs: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class CheckInput:
    chapters: list[ChapterFacts]
    snapshot: dict
    statements: list[StatementFacts]
    days: Decimal
    risk_days: Decimal
    cost: Decimal
    price: Decimal
    price_required: bool
    commercials_confirmed: bool
    map_revision: int = 0
    revoked_block_ids: set[int] = field(default_factory=set)


Rule = Callable[[CheckInput], list[RuleFinding]]


def chapter_target(key: str) -> str:
    return f"chapter:{key}"


def live_stories(snapshot: dict) -> list[dict]:
    return [
        story
        for activity in snapshot["activities"]
        if not activity["archived"]
        for task in activity["tasks"]
        if not task["archived"]
        for story in task["stories"]
        if not story["archived"]
    ]


def _is_empty(content: Content) -> bool:
    if isinstance(content, ProseContent):
        return not content_lines(content)
    if isinstance(content, TableContent):
        return not content.rows
    return False


def required_chapters(inp: CheckInput) -> list[RuleFinding]:
    return [
        RuleFinding(
            "required_chapter_empty",
            BLOCKER,
            chapter_target(c.key),
            f"Das Pflichtkapitel „{c.title}“ ist noch leer.",
        )
        for c in inp.chapters
        if c.required and _is_empty(c.content)
    ]


def _checked(inp: CheckInput, check: str) -> list[ChapterFacts]:
    return [chapter for chapter in inp.chapters if check in chapter.checks]


def stories_present(inp: CheckInput) -> list[RuleFinding]:
    """A chapter that must hold all stories needs at least one on the map."""
    if live_stories(inp.snapshot):
        return []
    return [
        RuleFinding(
            "no_stories",
            BLOCKER,
            chapter_target(chapter.key),
            "Die Story Map enthält noch keine Stories.",
        )
        for chapter in _checked(inp, CONTAINS_ALL_STORIES)
    ]


def _texts(inp: CheckInput, chapter: ChapterFacts) -> list[str]:
    """What a chapter shows; a stories chapter shows the story descriptions."""
    if isinstance(chapter.content, StoriesContent):
        return [s.get("description", "") for s in live_stories(inp.snapshot)]
    return content_lines(chapter.content)


def acceptance_criteria(inp: CheckInput) -> list[RuleFinding]:
    """Chapter text that reads like acceptance criteria (spec 8.4)."""
    return [
        RuleFinding(
            "acceptance_criteria",
            WARNING,
            chapter_target(chapter.key),
            f"„{chapter.title}“ enthält Akzeptanzkriterien. Das Angebot nennt "
            "keine Akzeptanzkriterien.",
        )
        for chapter in _checked(inp, NO_ACCEPTANCE_CRITERIA)
        if any(
            pattern.search(text)
            for text in _texts(inp, chapter)
            for pattern in CRITERIA_PATTERNS
        )
    ]


def story_format(inp: CheckInput) -> list[RuleFinding]:
    return [
        RuleFinding(
            "story_format",
            BLOCKER,
            f"story:{s['key']}",
            f"{s['key']}: {problems[0]}",
        )
        for s in live_stories(inp.snapshot)
        if (problems := story_problems(s["title"], s["role"], s["goal"], s["benefit"]))
    ]


def unplaced_stories(inp: CheckInput) -> list[RuleFinding]:
    return [
        RuleFinding(
            "story_unplaced",
            WARNING,
            f"story:{s['key']}",
            f"{s['key']} gehört zu keiner Aufgabe und Aktivität.",
        )
        for s in inp.snapshot.get("unassigned", [])
        if not s["archived"]
    ]


def review_marks(inp: CheckInput) -> list[RuleFinding]:
    return [
        RuleFinding(
            "chapter_needs_review",
            WARNING,
            chapter_target(c.key),
            f"„{c.title}“ ist erneut zu prüfen. {c.review_reason}".strip(),
        )
        for c in inp.chapters
        if c.needs_review
    ]


def placeholders(inp: CheckInput) -> list[RuleFinding]:
    return [
        RuleFinding(
            "placeholder",
            BLOCKER,
            chapter_target(c.key),
            f"„{c.title}“ enthält noch einen offenen Platzhalter.",
        )
        for c in inp.chapters
        if PLACEHOLDER.search("\n".join(content_lines(c.content)))
    ]


def statements(inp: CheckInput) -> list[RuleFinding]:
    findings = [
        RuleFinding(
            "conflict_open",
            BLOCKER,
            f"statement:{s.id}",
            f"Offener Widerspruch: {s.text}",
        )
        for s in inp.statements
        if s.type == StatementType.CONFLICT and not s.confirmed
    ]
    open_requirements = [
        s
        for s in inp.statements
        if s.type == StatementType.REQUIREMENT and not s.confirmed
    ]
    if open_requirements:
        count = len(open_requirements)
        noun = "Anforderung ist" if count == 1 else "Anforderungen sind"
        findings.append(
            RuleFinding(
                "requirement_open",
                NOTE,
                "workspace",
                f"{count} {noun} noch nicht fachlich bestätigt.",
            )
        )
    return findings


def commercials(inp: CheckInput) -> list[RuleFinding]:
    checked = _checked(inp, COMMERCIALS_CONFIRMED)
    target = chapter_target(checked[0].key) if checked else "workspace"
    findings: list[RuleFinding] = []
    if inp.price_required and not inp.commercials_confirmed:
        findings.append(
            RuleFinding(
                "commercials_unconfirmed",
                BLOCKER,
                target,
                "Die Kalkulation ist nicht bestätigt.",
            )
        )
    if inp.price_required and inp.price <= 0:
        findings.append(
            RuleFinding(
                "commercials_invalid",
                BLOCKER,
                target,
                "Der empfohlene Preis fehlt.",
                "price",
            )
        )
    if inp.price > 0 and inp.price < inp.cost:
        findings.append(
            RuleFinding(
                "commercials_invalid",
                BLOCKER,
                target,
                "Der empfohlene Preis liegt unter den Herstellkosten.",
                "margin",
            )
        )
    return findings


def _amount(match: re.Match[str]) -> tuple[Decimal, bool] | None:
    whole = match.group(1).replace(".", "")
    text = f"{whole}.{match.group(2)}" if match.group(2) else whole
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    scale = (match.group(3) or "").lower()
    value *= SCALES.get(scale, Decimal(1000) if scale == "t" else Decimal(1))
    return value, match.group(4).lower().startswith(DAY_UNITS)


def _word_amount(match: re.Match[str]) -> tuple[Decimal, bool]:
    """``vierzig Personentage`` or ``dreiundzwanzig PT``."""
    word = match.group(2).lower()
    unit = NUMBER_WORDS.get(word, 0) or TENS.get(word, 0)
    value = unit + NUMBER_WORDS.get((match.group(1) or "").lower(), 0)
    return Decimal(value), match.group(3).lower().startswith(DAY_UNITS)


def _typed_amounts(text: str) -> list[tuple[str, Decimal, bool]]:
    found = [
        (m.group(0), *parsed) for m in AMOUNT.finditer(text) if (parsed := _amount(m))
    ]
    found.extend((m.group(0), *_word_amount(m)) for m in WORD_AMOUNT.finditer(text))
    return found


def free_numbers(inp: CheckInput) -> list[RuleFinding]:
    """Typed amounts that differ from the structured values (A18)."""
    days = {inp.days, inp.risk_days, inp.days + inp.risk_days}
    money = {inp.cost, inp.price}
    findings: list[RuleFinding] = []
    for chapter in inp.chapters:
        if not isinstance(chapter.content, ProseContent):
            continue
        text = "\n".join(content_lines(chapter.content))
        for shown, value, is_days in _typed_amounts(text):
            if value not in (days if is_days else money):
                findings.append(
                    RuleFinding(
                        "free_number_mismatch",
                        BLOCKER,
                        chapter_target(chapter.key),
                        f"„{shown.strip()}“ weicht von der Kalkulation ab. "
                        "Nutzen Sie den gebundenen Wert oder korrigieren Sie den Text.",
                        shown.strip(),
                    )
                )
    return findings


def revoked_sources(inp: CheckInput) -> list[RuleFinding]:
    if not inp.revoked_block_ids:
        return []
    revoked = inp.revoked_block_ids
    findings = [
        RuleFinding(
            "source_revoked",
            WARNING,
            f"story:{s['key']}",
            f"{s['key']} stützt sich auf eine zurückgezogene Quelle.",
        )
        for s in live_stories(inp.snapshot)
        if revoked & set(s["source_refs"])
    ]
    findings.extend(
        RuleFinding(
            "source_revoked",
            WARNING,
            f"statement:{s.id}",
            f"Eine Aussage stützt sich auf eine zurückgezogene Quelle: {s.text}",
        )
        for s in inp.statements
        if revoked & set(s.source_refs)
    )
    return findings


RULES: tuple[Rule, ...] = (
    required_chapters,
    stories_present,
    acceptance_criteria,
    story_format,
    unplaced_stories,
    review_marks,
    placeholders,
    statements,
    commercials,
    free_numbers,
    revoked_sources,
)


def run_rules(inp: CheckInput) -> list[RuleFinding]:
    return [finding for rule in RULES for finding in rule(inp)]
