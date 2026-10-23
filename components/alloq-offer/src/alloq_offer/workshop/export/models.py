"""Inputs of the Word renderer."""

from __future__ import annotations

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
    scope: str
    group: str = ""


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
