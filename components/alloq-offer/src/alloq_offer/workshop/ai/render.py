"""Sources as clearly delimited data for a prompt."""

from alloq_offer.workshop.ai.port import (
    ChapterRequest,
    MapRequest,
    ReviewRequest,
    SourceText,
)

TABLE_TASK = "Liefere Tabellenzeilen mit genau diesen Spalten:"
TRUNCATED = "[Weitere Quellen wurden wegen der Länge ausgelassen.]"
TRUNCATED_CHAPTERS = "[Weitere Kapitel wurden wegen der Länge ausgelassen.]"


def render_sources(sources: list[SourceText], max_chars: int) -> str:
    """One ``<quelle>`` block per source; whole sources are dropped past the budget."""
    parts: list[str] = []
    used = 0
    for source in sources:
        lines = [f'<quelle id="{source.id}" art="{_attr(source.kind)}">']
        lines.append(f"Titel: {_tags(source.title)}")
        for block in source.blocks:
            speaker = f"{_tags(block.speaker)}: " if block.speaker else ""
            label = f" ({_tags(block.label)})" if block.label else ""
            lines.append(f"[B{block.id}]{label} {speaker}{_tags(block.text)}")
        lines.extend(f"[Lücke] {_tags(gap)}" for gap in source.gaps)
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
                f"    {story['key']} {story['title']}: {story['sentence']}"
                for story in task["stories"]
                if not story["archived"]
            )
    return "\n".join(lines)


def _tags(text: str) -> str:
    """Neutralise angle brackets so text cannot close or open a delimiter."""
    return text.replace("<", "&lt;").replace(">", "&gt;")


def _attr(text: str) -> str:
    """A value inside ``attribute="…"``; quotes cannot end it early."""
    return _tags(text.replace("&", "&amp;")).replace('"', "&quot;")


def render_chapter(request: ChapterRequest, max_chars: int) -> str:
    """The chapter task with map and briefing as delimited data."""
    parts = [
        f'<kapitel titel="{_attr(request.title)}">',
        f"Leitfrage: {_tags(request.guiding_question)}",
        *(f"Regel: {_tags(rule)}" for rule in request.rules),
        *(f"Pflichtangabe: {_tags(info)}" for info in request.required_info),
        *(
            [f"{TABLE_TASK} {' | '.join(map(_tags, request.columns))}"]
            if request.columns
            else []
        ),
        "</kapitel>",
    ]
    if request.prompt_text.strip():
        parts += [
            "<kapitelanweisung>",
            _tags(request.prompt_text),
            "</kapitelanweisung>",
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
    """Map, briefing and chapters as delimited data for the review.

    Past the budget whole chapters are left out, so no data section stays open.
    """
    parts = ["<map>", _tags(request.map_outline)[:max_chars], "</map>"]
    parts += ["<briefing>", *map(_tags, request.statements), "</briefing>"]
    used = sum(len(part) + 1 for part in parts)
    for chapter in request.chapters:
        section = "\n".join(
            [
                f'<kapitel key="{_attr(chapter.key)}" titel="{_attr(chapter.title)}">',
                *map(_tags, chapter.lines),
                "</kapitel>",
            ]
        )
        if used + len(section) > max_chars:
            parts.append(TRUNCATED_CHAPTERS)
            break
        parts.append(section)
        used += len(section) + 1
    return "\n".join(parts)


def render_map_request(request: MapRequest, max_chars: int) -> str:
    """Instruction, current map and briefing, then the sources as delimited data."""
    parts = ["<anweisung>", _tags(request.instruction), "</anweisung>"]
    parts += ["<map>", _tags(request.map_outline), "</map>"]
    parts += ["<briefing>", *map(_tags, request.statements), "</briefing>"]
    head = "\n".join(parts)
    sources = render_sources(request.sources, max(max_chars - len(head), 0))
    return f"{head}\n\n{sources}"
