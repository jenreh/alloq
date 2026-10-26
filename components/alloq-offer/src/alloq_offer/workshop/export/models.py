"""Inputs of the Word renderer."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from alloq_offer.workshop.content.schema import (
    CalcContent,
    ProseContent,
    StoriesContent,
    TableContent,
)

UNCONFIRMED_MARK = "[nicht bestätigt]"
MISSING_MARK = "[Wert fehlt]"
NO_GROUP_LABEL = "Ohne Zuordnung"


class RenderError(ValueError):
    """Rendering failed; nothing is silently dropped."""


class UnsupportedContentError(RenderError):
    """A chapter holds content the renderer cannot represent."""


@dataclass(frozen=True)
class ResolvedStory:
    key: str
    title: str
    sentence: str
    group: str = ""
    slice: str = ""
    slice_order: int = 0


def group_stories(
    stories: Sequence[ResolvedStory], by: str
) -> dict[str, list[ResolvedStory]]:
    """Stories by activity (map order) or by slice (slice order); stories
    without one come last."""
    groups: dict[str, list[ResolvedStory]] = {}
    for story in stories:
        title = story.slice if by == "slice" else story.group
        groups.setdefault(title or NO_GROUP_LABEL, []).append(story)
    if by != "slice":
        return groups
    order = {story.slice: story.slice_order for story in stories}
    return dict(
        sorted(
            groups.items(),
            key=lambda item: (item[0] == NO_GROUP_LABEL, order.get(item[0], 0)),
        )
    )


@dataclass(frozen=True)
class ResolvedValue:
    text: str | None
    confirmed: bool = False

    def display(self) -> str:
        if self.text is None or not self.text.strip():
            return MISSING_MARK
        if not self.confirmed:
            return f"{self.text} {UNCONFIRMED_MARK}"
        return self.text


@dataclass(frozen=True)
class ChapterInput:
    key: str
    title: str
    level: int
    content: ProseContent | TableContent | StoriesContent | CalcContent


@dataclass
class RenderContext:
    cover: dict[str, str]
    stories: list[ResolvedStory] = field(default_factory=list)
    values: dict[str, ResolvedValue] = field(default_factory=dict)
    draft: bool = True
    open_points: list[str] = field(default_factory=list)
