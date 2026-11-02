"""The port to the language model; the rest of the workshop only knows this."""

from dataclasses import dataclass, field
from typing import Protocol

from alloq_offer.workshop.ai.schemas import (
    ProposedBriefing,
    ProposedChapter,
    ProposedMap,
    ProposedReview,
    ProposedTable,
)


@dataclass(frozen=True)
class BlockText:
    id: int
    text: str
    label: str = ""
    speaker: str | None = None


@dataclass(frozen=True)
class SourceText:
    """One source as data for a prompt."""

    id: int
    title: str
    kind: str
    blocks: list[BlockText] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChapterRequest:
    """What the model gets to know when it drafts or reworks one chapter."""

    title: str
    guiding_question: str
    rules: list[str]
    current_lines: list[str]
    instruction: str
    map_outline: str
    statements: list[str]
    required_info: list[str] = field(default_factory=list)
    prompt_text: str = ""
    # Set for a table chapter: the model fills rows for exactly these columns.
    columns: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReviewChapter:
    key: str
    title: str
    lines: list[str]


@dataclass(frozen=True)
class ReviewRequest:
    """The offer as the review reads it: map, briefing and written chapters."""

    map_outline: str
    statements: list[str]
    chapters: list[ReviewChapter]


@dataclass(frozen=True)
class MapRequest:
    """A wish for more of the map: the current map, the briefing and the sources."""

    instruction: str
    map_outline: str
    statements: list[str]
    sources: list[SourceText]


class AiUnavailableError(RuntimeError):
    """No model is configured or it cannot be reached for good."""


class AiSetupError(AiUnavailableError):
    """The setup is incomplete; the message is German and shown to users."""


class AiTransientError(RuntimeError):
    """The model call may work on a later attempt (timeout, rate limit)."""


class OfferAi(Protocol):
    model_name: str
    map_prompt_version: str
    briefing_prompt_version: str

    async def propose_map(self, sources: list[SourceText]) -> ProposedMap: ...

    async def propose_briefing(self, sources: list[SourceText]) -> ProposedBriefing: ...


class ChapterAi(Protocol):
    model_name: str
    chapter_prompt_version: str

    async def propose_chapter(self, request: ChapterRequest) -> ProposedChapter: ...

    async def propose_table(self, request: ChapterRequest) -> ProposedTable: ...


class ReviewAi(Protocol):
    model_name: str
    review_prompt_version: str

    async def propose_review(self, request: ReviewRequest) -> ProposedReview: ...


class MapAdditionAi(Protocol):
    model_name: str
    map_additions_prompt_version: str

    async def propose_map_additions(self, request: MapRequest) -> ProposedMap: ...
