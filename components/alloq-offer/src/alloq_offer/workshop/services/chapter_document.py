"""The offer as one document: every chapter with what its block shows read-only."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

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
from alloq_offer.workshop.repositories import job_repo, workspace_repo
from alloq_offer.workshop.services.chapter_draft import DRAFT_CHAPTERS_JOB
from alloq_offer.workshop.services.chapters import (
    ChapterService,
    chapter_detail,
    current_revisions,
)
from alloq_offer.workshop.services.commercials import resolve_values
from alloq_offer.workshop.services.export_snapshot import resolve_stories
from alloq_offer.workshop.services.map_apply import current_snapshot
from alloq_offer.workshop.services.outline import removed_chapters
from alloq_offer.workshop.services.templates import load_template


@dataclass(frozen=True)
class OfferDocument:
    chapters: list[dict[str, Any]]
    frame_before: list[str]
    frame_after: list[str]
    # What ``ChapterService.load`` returns, for every chapter of the outline.
    details: dict[str, dict[str, Any]] = field(default_factory=dict)
    removed: list[dict[str, str]] = field(default_factory=list)
    draft_job: str = ""


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
    """Everything the chapter tab shows, read in one session."""
    async with sessions() as session:
        found = await workspace_repo.find_with_offer(session, offer_id)
        if found is None:
            return None
        workspace, offer = found
        outline = await ChapterService(sessions, offer_id, user).outline(
            session, workspace
        )
        template = await load_template(
            session, workspace.template_key, workspace.template_version
        )
        stored = await current_revisions(session, outline.chapters)
        stories = resolve_stories(await current_snapshot(session, workspace))
        removed = await removed_chapters(session, offer_id)
        job = await job_repo.find_latest(session, offer_id, DRAFT_CHAPTERS_JOB)
    values = resolve_values(offer, workspace)
    blocks = {
        c.chapter_key: render_block(
            parse_content(stored[c.id].content), stories, values
        )
        for c in outline.chapters
    }
    return OfferDocument(
        chapters=[{**view, **blocks.get(view["key"], {})} for view in outline.views],
        frame_before=template.frame_before,
        frame_after=template.frame_after,
        details={
            c.chapter_key: chapter_detail(c, stored[c.id], outline.proposals)
            for c in outline.chapters
        },
        removed=removed,
        draft_job=job.status if job is not None else "",
    )
