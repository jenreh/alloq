"""Sources as clearly delimited data for a prompt."""

from alloq_offer.workshop.ai.port import SourceText

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
