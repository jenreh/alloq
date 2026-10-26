"""The offer as one document: every chapter with what its block shows read-only."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from alloq_offer.entities import OfferEntity
from alloq_offer.workshop.content.editor_io import content_to_html
from alloq_offer.workshop.content.schema import (
    BOUND_FIELDS,
    CalcContent,
    ProseContent,
    TableContent,
    parse_content,
    plain_text,
)
from alloq_offer.workshop.content.text import Content
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.export.models import (
    ResolvedStory,
    ResolvedValue,
    group_stories,
)
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.chapters import (
    ChapterService,
    current_revisions,
    live_chapters,
)
from alloq_offer.workshop.services.commercials import resolve_values
from alloq_offer.workshop.services.export_snapshot import resolve_stories
from alloq_offer.workshop.services.map_apply import snapshot_map
from alloq_offer.workshop.services.templates import load_template


@dataclass(frozen=True)
class OfferDocument:
    chapters: list[dict[str, Any]]
    frame_before: list[str]
    frame_after: list[str]


def render_block(
    content: Content,
    stories: Sequence[ResolvedStory],
    values: Mapping[str, ResolvedValue],
) -> dict[str, Any]:
    """What a block shows when it is not being edited."""
    if isinstance(content, ProseContent):
        return {"html": content_to_html(content)}
    if isinstance(content, TableContent):
        return {
            "columns": content.columns,
            "rows": [[plain_text(cell) for cell in row] for row in content.rows],
        }
    if isinstance(content, CalcContent):
        return {
            "intro": plain_text(content.intro),
            "values": [
                {
                    "label": row.label,
                    "field": row.field,
                    "value": values[row.field].display(),
                }
                for row in content.rows
            ],
        }
    return {
        "group_by": content.group_by,
        "groups": [
            {
                "title": title,
                "stories": [
                    {"key": s.key, "title": s.title, "sentence": s.sentence}
                    for s in items
                ],
            }
            for title, items in group_stories(stories, content.group_by).items()
        ],
    }


def free_fields(rows: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    """Bound fields a calc block does not show yet, as select options."""
    used = {row["field"] for row in rows}
    return [
        {"value": field, "label": label}
        for field, label in BOUND_FIELDS.items()
        if field not in used
    ]


async def load_document(
    sessions: SessionFactory, offer_id: int, user: str
) -> OfferDocument | None:
    """Outline, block contents and the fixed frame of the offer."""
    views = await ChapterService(sessions, offer_id, user).open()
    async with sessions() as session:
        workspace = await workspace_repo.find_by_offer(session, offer_id)
        offer = await session.get(OfferEntity, offer_id)
        if workspace is None or offer is None:
            return None
        template = await load_template(
            session, workspace.template_key, workspace.template_version
        )
        chapters = await live_chapters(session, offer_id)
        stored = await current_revisions(session, chapters)
        stories = resolve_stories(await snapshot_map(session, workspace))
        values = resolve_values(offer, workspace)
    blocks = {
        c.chapter_key: render_block(
            parse_content(stored[c.id].content), stories, values
        )
        for c in chapters
    }
    return OfferDocument(
        chapters=[{**view, **blocks.get(view["key"], {})} for view in views],
        frame_before=template.frame_before,
        frame_after=template.frame_after,
    )
