"""Sources as clearly delimited data for a prompt."""

from alloq_offer.workshop.ai.port import (
    ChapterRequest,
    MapRequest,
    ReviewRequest,
    SourceText,
)

TRUNCATED = "[Weitere Quellen wurden wegen der Länge ausgelassen.]"


def _escape(text: str) -> str:
    return text.replace("</quelle>", "<\\/quelle>").replace("<quelle", "<\\quelle")


def render_sources(sources: list[SourceText], max_chars: int) -> str:
    """One ``<quelle>`` block per source; whole sources are dropped past the budget."""
    parts: list[str] = []
    used = 0
    for source in sources:
        lines = [f'<quelle id="{source.id}" art="{_escape(source.kind)}">']
        lines.append(f"Titel: {_escape(source.title)}")
        for block in source.blocks:
            speaker = f"{block.speaker}: " if block.speaker else ""
            label = f" ({block.label})" if block.label else ""
            lines.append(f"[B{block.id}]{label} {speaker}{_escape(block.text)}")
        lines.extend(f"[Lücke] {_escape(gap)}" for gap in source.gaps)
        lines.append("</quelle>")
        text = "\n".join(lines)
        if parts and used + len(text) > max_chars:
            parts.append(TRUNCATED)
            break
        parts.append(text)
        used += len(text)
    return "\n\n".join(parts)


CONFIRMED_MARK = " (fachlich bestätigt)"


def statement_line(type_: str, text: str, confirmed: bool) -> str:
    """A briefing statement as one prompt line."""
    return f"{type_}: {text}" + (CONFIRMED_MARK if confirmed else "")


def map_outline(snapshot: dict) -> str:
    """The live part of a map snapshot as indented text: activities, tasks, stories."""
    lines: list[str] = []
    if snapshot["vision"]:
        lines.append(f"Vision: {snapshot['vision']}")
    for activity in snapshot["activities"]:
        if activity["archived"]:
            continue
        lines.append(f"Aktivität: {activity['title']}")
        for task in activity["tasks"]:
            if task["archived"]:
                continue
            lines.append(f"  Aufgabe: {task['title']}")
            lines.extend(
                f"    {story['key']} [{story['scope']}] {story['title']}: "
                f"{story['sentence']}"
                for story in task["stories"]
                if not story["archived"]
            )
    return "\n".join(lines)


def _tags(text: str) -> str:
    """Neutralise angle brackets so text cannot close or open a delimiter."""
    return text.replace("<", "&lt;").replace(">", "&gt;")


def render_chapter(request: ChapterRequest, max_chars: int) -> str:
    """The chapter task with map and briefing as delimited data."""
    parts = [
        f'<kapitel titel="{_tags(request.title)}">',
        f"Leitfrage: {_tags(request.guiding_question)}",
        *(f"Regel: {_tags(rule)}" for rule in request.rules),
        "</kapitel>",
    ]
    if request.current_lines:
        lines = [_tags(line) for line in request.current_lines]
        parts += ["<aktueller_text>", *lines, "</aktueller_text>"]
    if request.instruction:
        parts += ["<anweisung>", _tags(request.instruction), "</anweisung>"]
    parts += ["<map>", _tags(request.map_outline)[:max_chars], "</map>"]
    parts += ["<briefing>", *map(_tags, request.statements), "</briefing>"]
    return "\n".join(parts)


def render_review(request: ReviewRequest, max_chars: int) -> str:
    """Map, briefing and chapters as delimited data for the review."""
    parts = ["<map>", _tags(request.map_outline), "</map>"]
    parts += ["<briefing>", *map(_tags, request.statements), "</briefing>"]
    for chapter in request.chapters:
        parts += [
            f'<kapitel key="{_tags(chapter.key)}" titel="{_tags(chapter.title)}">'
        ]
        parts += [*map(_tags, chapter.lines), "</kapitel>"]
    return "\n".join(parts)[:max_chars]


def render_map_request(request: MapRequest, max_chars: int) -> str:
    """Instruction, current map and briefing, then the sources as delimited data."""
    parts = ["<anweisung>", _tags(request.instruction), "</anweisung>"]
    parts += ["<map>", _tags(request.map_outline), "</map>"]
    parts += ["<briefing>", *map(_tags, request.statements), "</briefing>"]
    head = "\n".join(parts)
    sources = render_sources(request.sources, max(max_chars - len(head), 0))
    return f"{head}\n\n{sources}"
