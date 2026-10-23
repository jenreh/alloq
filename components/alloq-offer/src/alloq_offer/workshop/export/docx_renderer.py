"""Render the offer document: cover and legal tail from the template layout,
chapters from typed content. The story map graphic is never rendered."""

from __future__ import annotations

import io
from collections.abc import Sequence

from docxtpl import DocxTemplate
from jinja2 import Environment, StrictUndefined

from alloq_offer.workshop.content.schema import Run
from alloq_offer.workshop.export.chapter_renderers import RENDERERS, Writer
from alloq_offer.workshop.export.models import (
    ChapterInput,
    RenderContext,
    RenderError,
    UnsupportedContentError,
)
from alloq_offer.workshop.export.template_package import (
    TemplatePackage,
    find_anchor,
)

DRAFT_MARKER = "ENTWURF – nicht zur Weitergabe an den Kunden"


def render_document(
    package: TemplatePackage,
    chapters: Sequence[ChapterInput],
    ctx: RenderContext,
) -> bytes:
    template = DocxTemplate(io.BytesIO(package.layout_bytes))
    template.render(
        dict(ctx.cover),
        jinja_env=Environment(autoescape=True, undefined=StrictUndefined),
    )
    document = template.docx
    if document is None:
        raise RenderError("Die Vorlage konnte nicht geladen werden.")
    anchor = find_anchor(document)
    writer = Writer(document, anchor)
    if ctx.draft:
        writer.paragraph([Run(text=DRAFT_MARKER, bold=True)])
    for chapter in chapters:
        renderer = RENDERERS.get(chapter.content.chapter_type)
        if renderer is None:
            raise UnsupportedContentError(chapter.content.chapter_type)
        writer.heading(chapter.title, chapter.level)
        renderer(writer, chapter, ctx)
    anchor._p.getparent().remove(anchor._p)  # noqa: SLF001

    out = io.BytesIO()
    document.save(out)
    return out.getvalue()
