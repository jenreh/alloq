"""Inputs of the Word renderer."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from alloq_offer.workshop.content.schema import AnyContent, StoriesContent

UNCONFIRMED_MARK = "[nicht bestätigt]"
MISSING_MARK = "[Wert fehlt]"
NO_GROUP_LABEL = "Ohne Zuordnung"
NO_SLICE_LABEL = "Ohne Schnitt"
NO_SLICE_VALUE = "none"


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
    activity_id: int = 0
    slice_id: int = 0


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


def filter_stories(
    stories: Sequence[ResolvedStory], content: StoriesContent
) -> list[ResolvedStory]:
    """The stories a stories chapter shows; empty filters let every story pass."""
    return [s for s in stories if content.shows(s.activity_id, s.slice_id)]


def _counted(entries: dict[int, tuple[str, int]]) -> list[dict[str, str]]:
    return [
        {"value": str(key), "label": f"{title} ({count})"}
        for key, (title, count) in entries.items()
    ]


def story_filter_options(stories: Sequence[ResolvedStory]) -> dict[str, list]:
    """Columns and slices of the map with their story counts, as select options."""
    activities: dict[int, tuple[str, int]] = {}
    slices: dict[int, tuple[str, int]] = {}
    unsliced = 0
    for story in stories:
        if story.activity_id:
            title, count = activities.get(story.activity_id, (story.group, 0))
            activities[story.activity_id] = (title, count + 1)
        if story.slice_id:
            title, count = slices.get(story.slice_id, (story.slice, 0))
            slices[story.slice_id] = (title, count + 1)
        else:
            unsliced += 1
    ordered = dict(
        sorted(slices.items(), key=lambda item: _slice_order(stories, item[0]))
    )
    slice_options = _counted(ordered)
    if unsliced:
        slice_options.append(
            {"value": NO_SLICE_VALUE, "label": f"{NO_SLICE_LABEL} ({unsliced})"}
        )
    return {"activities": _counted(activities), "slices": slice_options}


def _slice_order(stories: Sequence[ResolvedStory], slice_id: int) -> int:
    return next((s.slice_order for s in stories if s.slice_id == slice_id), 0)


def filter_label(stories: Sequence[ResolvedStory], content: StoriesContent) -> str:
    """The active filter in words, e.g. "Spalten: A · Schnitte: MVP"."""
    activities = {s.activity_id: s.group for s in stories}
    slices = {s.slice_id: s.slice for s in stories}
    parts = []
    names = [activities[i] for i in content.activity_ids if i in activities]
    if names:
        parts.append("Spalten: " + ", ".join(names))
    names = [slices[i] for i in content.slice_ids if i in slices]
    if content.unsliced:
        names.append(NO_SLICE_LABEL)
    if names:
        parts.append("Schnitte: " + ", ".join(names))
    return " · ".join(parts)


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
    content: AnyContent


@dataclass
class RenderContext:
    cover: dict[str, str]
    stories: list[ResolvedStory] = field(default_factory=list)
    values: dict[str, ResolvedValue] = field(default_factory=dict)
    draft: bool = True
    open_points: list[str] = field(default_factory=list)
    # Bytes of the image chapters, by blob id.
    images: dict[int, bytes] = field(default_factory=dict)
