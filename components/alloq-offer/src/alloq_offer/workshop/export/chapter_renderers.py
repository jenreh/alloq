"""One renderer per chapter type, selected through a registry."""

from __future__ import annotations

import io
import re
from collections.abc import Callable

from docx.document import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml.text.run import CT_R
from docx.shared import Pt, RGBColor
from docx.text.paragraph import Paragraph as DocxParagraph

from alloq_offer.workshop.content.schema import (
    BOUND_FIELDS,
    TEXT_COLORS,
    BoundValue,
    BulletList,
    CalcContent,
    CodeBlock,
    Heading,
    ImageContent,
    Inline,
    OrderedList,
    Paragraph,
    ProseContent,
    Quote,
    Rule,
    Run,
    StoriesContent,
    TableBlock,
    TableContent,
    TaskList,
    plain_text,
)
from alloq_offer.workshop.export.models import (
    ChapterInput,
    RenderContext,
    RenderError,
    ResolvedValue,
    UnsupportedContentError,
    filter_stories,
    group_stories,
)

TABLE_STYLE = "arvato-Tabelle blau"
BULLET_STYLE = "Aufzählung 1"
ORDERED_STYLE = "List Number"
# List styles by depth; deeper lists keep the last one.
BULLET_STYLES = ("Aufzählung 1", "Aufzählung 2", "Aufzählung 3")
ORDERED_STYLES = ("List Number", "List Number 2", "List Number 3")
QUOTE_STYLE = "Quote"
LINK_STYLE = "Hyperlink"
CODE_FONT = "Consolas"
TASK_BOXES = {True: "☑ ", False: "☐ "}
CAPTION_STYLE = "Caption"
NO_STORIES_TEXT = "Die Story Map enthält keine Stories."
MISSING_IMAGE = "Ein Bild des Angebots fehlt im Speicher."
BAD_IMAGE = "Ein Bild des Angebots kann Word nicht lesen."
ALIGNMENTS = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
}
_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class Writer:
    """Appends content in front of the chapter anchor of a python-docx document."""

    def __init__(self, document: DocxDocument, anchor: DocxParagraph) -> None:
        self._doc = document
        self._anchor = anchor

    def _style(self, name: str) -> str:
        try:
            return self._doc.styles[name].name
        except KeyError as exc:
            raise RenderError(f"Formatvorlage fehlt in der Vorlage: {name}") from exc

    def _has_style(self, name: str) -> bool:
        try:
            self._doc.styles[name]
        except KeyError:
            return False
        return True

    def _place(self, element: object) -> None:
        self._anchor._p.addprevious(element)  # noqa: SLF001

    def runs(self, paragraph: DocxParagraph, runs: Inline) -> None:
        for run in runs:
            target = paragraph.add_run(_ILLEGAL_XML.sub("", run.text))
            font = target.font
            target.bold = run.bold or None
            target.italic = run.italic or None
            target.underline = run.underline or None
            font.strike = run.strike or None
            font.subscript = run.sub or None
            font.superscript = run.sup or None
            if run.code:
                font.name = CODE_FONT
            if run.highlight:
                font.highlight_color = WD_COLOR_INDEX.YELLOW
            if run.color:
                font.color.rgb = RGBColor.from_string(TEXT_COLORS[run.color][1:])
            if run.link:
                self._link(paragraph, target._r, run.link)  # noqa: SLF001

    def _link(self, paragraph: DocxParagraph, run: CT_R, url: str) -> None:
        """Wrap a written run into an external hyperlink."""
        relation = paragraph.part.relate_to(
            url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True
        )
        link = OxmlElement("w:hyperlink")
        link.set(qn("r:id"), relation)
        paragraph._p.append(link)  # noqa: SLF001
        link.append(run)
        if self._has_style(LINK_STYLE):
            r_pr = run.get_or_add_rPr()
            style = OxmlElement("w:rStyle")
            style.set(qn("w:val"), self._doc.styles[LINK_STYLE].style_id)
            r_pr.insert(0, style)

    def paragraph(
        self, runs: Inline, style: str | None = None, align: str = "left"
    ) -> DocxParagraph:
        paragraph = self._anchor.insert_paragraph_before(
            style=self._style(style) if style else None
        )
        if align != "left":
            paragraph.alignment = ALIGNMENTS[align]
        self.runs(paragraph, runs)
        return paragraph

    def heading(self, text: str, level: int, align: str = "left") -> None:
        paragraph = self._anchor.insert_paragraph_before(
            _ILLEGAL_XML.sub("", text), style=self._style(f"Heading {level}")
        )
        if align != "left":
            paragraph.alignment = ALIGNMENTS[align]

    def styled(self, runs: Inline, style: str, fallback: dict[str, bool]) -> None:
        """A paragraph in ``style``, or direct formatting when the layout lacks it."""
        if self._has_style(style):
            self.paragraph(runs, style)
        else:
            self.paragraph([run.model_copy(update=fallback) for run in runs])

    def code(self, text: str) -> None:
        paragraph = self._anchor.insert_paragraph_before()
        for index, line in enumerate(text.split("\n")):
            run = paragraph.add_run(_ILLEGAL_XML.sub("", line))
            run.font.name = CODE_FONT
            run.font.size = Pt(9)
            if index:
                run._r.addprevious(OxmlElement("w:br"))  # noqa: SLF001

    def rule(self) -> None:
        """An empty paragraph with a bottom border, as Word draws a line."""
        paragraph = self._anchor.insert_paragraph_before()
        borders = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        for key, value in (("val", "single"), ("sz", "6"), ("space", "1")):
            bottom.set(qn(f"w:{key}"), value)
        bottom.set(qn("w:color"), "auto")
        borders.append(bottom)
        paragraph._p.get_or_add_pPr().append(borders)  # noqa: SLF001

    def caption(self, runs: Inline) -> None:
        """The description below a table or picture; italic without the style."""
        self.styled(runs, CAPTION_STYLE, {"italic": True})

    def picture(self, data: bytes, width_percent: int, align: str) -> None:
        section = self._doc.sections[-1]
        usable = (section.page_width or 0) - (section.left_margin or 0)
        usable -= section.right_margin or 0
        paragraph = self._anchor.insert_paragraph_before()
        paragraph.alignment = ALIGNMENTS.get(align, WD_ALIGN_PARAGRAPH.CENTER)
        try:
            paragraph.add_run().add_picture(
                io.BytesIO(data), width=int(usable * width_percent / 100)
            )
        except Exception as exc:  # python-docx raises several image errors
            raise RenderError(BAD_IMAGE) from exc

    def table(self, header: list[Inline], rows: list[list[Inline]]) -> None:
        table = self._doc.add_table(rows=1 + len(rows), cols=len(header))
        table.style = self._doc.styles[self._style(TABLE_STYLE)]
        for index, cell_runs in enumerate(header):
            self.runs(table.rows[0].cells[index].paragraphs[0], cell_runs)
        for row_index, row in enumerate(rows, start=1):
            for index, cell_runs in enumerate(row):
                self.runs(table.rows[row_index].cells[index].paragraphs[0], cell_runs)
        tr_pr = table.rows[0]._tr.get_or_add_trPr()  # noqa: SLF001
        tr_pr.append(tr_pr.makeelement(qn("w:tblHeader"), {}))
        self._place(table._tbl)  # noqa: SLF001


Renderer = Callable[[Writer, ChapterInput, RenderContext], None]


def _text(value: str) -> Inline:
    return [Run(text=value)]


def _bold(value: str) -> Inline:
    return [Run(text=value, bold=True)]


def _resolve(ctx: RenderContext, field: str) -> ResolvedValue:
    return ctx.values.get(field, ResolvedValue(text=None))


def _render_list(
    writer: Writer, block: BulletList | OrderedList | TaskList, depth: int = 0
) -> None:
    styles = ORDERED_STYLES if isinstance(block, OrderedList) else BULLET_STYLES
    style = styles[min(depth, len(styles) - 1)]
    for item in block.items:
        runs = item.runs
        if isinstance(block, TaskList):
            runs = [Run(text=TASK_BOXES[item.checked]), *runs]
        writer.paragraph(runs, style)
        for child in item.children:
            _render_list(writer, child, depth + 1)


def _render_prose(writer: Writer, chapter: ChapterInput, ctx: RenderContext) -> None:
    content = chapter.content
    if not isinstance(content, ProseContent):
        raise UnsupportedContentError(chapter.key)
    inner_min = min(chapter.level + 1, 4)
    for block in content.blocks:
        match block:
            case Paragraph():
                writer.paragraph(block.runs, align=block.align)
            case Heading():
                level = max(block.level, inner_min)
                writer.heading(plain_text(block.runs), level, block.align)
            case BulletList() | OrderedList() | TaskList():
                _render_list(writer, block)
            case Quote():
                for runs in block.paragraphs:
                    writer.styled(runs, QUOTE_STYLE, {"italic": True})
            case CodeBlock():
                writer.code(block.text)
            case Rule():
                writer.rule()
            case TableBlock():
                writer.table(block.header, block.rows)
            case BoundValue():
                label = BOUND_FIELDS[block.field]
                writer.paragraph(
                    _text(f"{label}: {_resolve(ctx, block.field).display()}")
                )
            case _:
                raise UnsupportedContentError(type(block).__name__)


def _render_table(writer: Writer, chapter: ChapterInput, _ctx: RenderContext) -> None:
    content = chapter.content
    if not isinstance(content, TableContent):
        raise UnsupportedContentError(chapter.key)
    writer.table([_bold(c) for c in content.columns], content.rows)
    # Table chapters have no heading; an older titled one keeps its title here.
    caption = content.description or _text(chapter.title.strip())
    if plain_text(caption).strip():
        writer.caption(caption)


def _render_image(writer: Writer, chapter: ChapterInput, ctx: RenderContext) -> None:
    content = chapter.content
    if not isinstance(content, ImageContent):
        raise UnsupportedContentError(chapter.key)
    if content.blob_id is None:
        return
    data = ctx.images.get(content.blob_id)
    if data is None:
        raise RenderError(MISSING_IMAGE)
    writer.picture(data, content.width, content.align)
    if plain_text(content.description).strip():
        writer.caption(content.description)


def _render_stories(writer: Writer, chapter: ChapterInput, ctx: RenderContext) -> None:
    content = chapter.content
    if not isinstance(content, StoriesContent):
        raise UnsupportedContentError(chapter.key)
    stories = filter_stories(ctx.stories, content)
    if not stories:
        writer.paragraph(_text(NO_STORIES_TEXT))
        return
    heading_level = min(chapter.level + 1, 4)
    for group, items in group_stories(stories, content.group_by).items():
        writer.heading(group, heading_level)
        for story in items:
            writer.paragraph(_bold(f"{story.key} – {story.title}"))
            writer.paragraph(_text(story.sentence))


def _render_calc(writer: Writer, chapter: ChapterInput, ctx: RenderContext) -> None:
    content = chapter.content
    if not isinstance(content, CalcContent):
        raise UnsupportedContentError(chapter.key)
    if content.intro:
        writer.paragraph(content.intro)
    rows = [
        [_text(row.label), _text(_resolve(ctx, row.field).display())]
        for row in content.rows
    ]
    writer.table([_bold("Position"), _bold("Wert")], rows)


RENDERERS: dict[str, Renderer] = {
    "prose": _render_prose,
    "table": _render_table,
    "stories": _render_stories,
    "calc": _render_calc,
    "image": _render_image,
}
