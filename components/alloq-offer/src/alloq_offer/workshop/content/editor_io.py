"""Editor HTML <-> canonical content tree (A06).

The rich text editor emits HTML. Only the blocks of the content model are
accepted; anything else is reported, never dropped quietly.
"""

from html import escape
from html.parser import HTMLParser

from alloq_offer.workshop.content.schema import (
    BOUND_FIELDS,
    BoundValue,
    BulletList,
    ContentValidationError,
    Heading,
    Inline,
    OrderedList,
    Paragraph,
    ProseContent,
    Run,
    TableBlock,
    plain_text,
)

BOUND_ATTR = "data-bound"
INLINE_TAGS = {"strong": "bold", "b": "bold", "em": "italic", "i": "italic"}
LIST_TAGS = {"ul", "ol"}
TABLE_PARTS = {"table", "thead", "tbody", "tr", "th", "td"}
HEADING_LEVELS = {"h3": 3, "h4": 4}
TEXT_CONTAINERS = {"p", "li", "th", "td", *HEADING_LEVELS}
VOID_TAGS = {"img", "hr"}
UNSUPPORTED_NAMES = {
    "h1": "Überschrift Ebene 1",
    "h2": "Überschrift Ebene 2",
    "h5": "Überschrift Ebene 5",
    "h6": "Überschrift Ebene 6",
    "a": "Links",
    "img": "Bilder",
    "blockquote": "Zitate",
    "pre": "Codeblöcke",
    "code": "Code",
    "u": "Unterstreichung",
    "s": "Durchstreichung",
    "hr": "Trennlinien",
}


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list = []
        self.errors: list[str] = []
        self._runs: Inline = []
        self._marks = {"bold": 0, "italic": 0}
        self._container = ""
        self._bound = ""
        self._list: tuple[str, list[Inline]] | None = None
        self._table: list[list[Inline]] | None = None
        self._row: list[Inline] | None = None
        self._skip = 0
        self._inner_p = 0

    def _fail(self, message: str) -> None:
        if message not in self.errors:
            self.errors.append(message)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in INLINE_TAGS:
            self._marks[INLINE_TAGS[tag]] += 1
        elif tag in LIST_TAGS:
            self._list = (tag, [])
        elif tag == "table":
            self._table = []
        elif tag == "tr":
            self._row = []
        elif tag in TEXT_CONTAINERS:
            self._open(tag, dict(attrs))
        elif tag == "br":
            self._text(" ")
        elif tag in UNSUPPORTED_NAMES:
            self._fail(f"Nicht erlaubt in Kapiteln: {UNSUPPORTED_NAMES[tag]}.")
            self._skip += tag not in VOID_TAGS
        elif tag not in TABLE_PARTS | {"div", "span"}:
            self._fail(f"Der Baustein „{tag}“ ist in Kapiteln nicht erlaubt.")

    def _open(self, tag: str, attrs: dict[str, str | None]) -> None:
        if tag == "p" and self._container:
            self._inner_p += 1  # editors wrap list items and cells in <p>
            return
        self._container = tag
        self._runs = []
        self._bound = attrs.get(BOUND_ATTR) or "" if tag == "p" else ""

    def handle_endtag(self, tag: str) -> None:
        if tag in INLINE_TAGS:
            self._marks[INLINE_TAGS[tag]] = max(self._marks[INLINE_TAGS[tag]] - 1, 0)
        elif tag in UNSUPPORTED_NAMES:
            self._skip = max(self._skip - (tag not in VOID_TAGS), 0)
        elif tag == "p" and self._inner_p:
            self._inner_p -= 1
        elif tag == self._container and tag in TEXT_CONTAINERS:
            self._close(tag)
        elif tag in LIST_TAGS and self._list is not None:
            kind, items = self._list
            block = BulletList if kind == "ul" else OrderedList
            self.blocks.append(block(items=items))
            self._list = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self._finish_table()

    def _close(self, tag: str) -> None:
        runs, self._runs, self._container = _merge(self._runs), [], ""
        if tag == "li" and self._list is not None:
            self._list[1].append(runs)
        elif tag in {"th", "td"} and self._row is not None:
            self._row.append(runs)
        elif tag in HEADING_LEVELS:
            self.blocks.append(Heading(level=HEADING_LEVELS[tag], runs=runs))  # ty: ignore[invalid-argument-type]
        elif tag == "p":
            if self._bound:
                self._add_bound()
            else:
                self.blocks.append(Paragraph(runs=runs))

    def _add_bound(self) -> None:
        if self._bound not in BOUND_FIELDS:
            self._fail(f"Unbekannter Kalkulationswert: {self._bound}")
        else:
            self.blocks.append(BoundValue(field=self._bound))
        self._bound = ""

    def _finish_table(self) -> None:
        rows, self._table = self._table or [], None
        if not rows:
            self._fail("Eine Tabelle braucht mindestens eine Kopfzeile.")
            return
        try:
            self.blocks.append(TableBlock(header=rows[0], rows=rows[1:]))
        except ValueError:
            self._fail(
                "Jede Tabellenzeile braucht gleich viele Zellen wie die Kopfzeile."
            )

    def _text(self, data: str) -> None:
        if self._container:
            self._runs.append(
                Run(
                    text=data,
                    bold=bool(self._marks["bold"]),
                    italic=bool(self._marks["italic"]),
                )
            )

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if data.strip() and not self._container:
            self._fail("Text außerhalb eines Absatzes ist nicht erlaubt.")
        self._text(data)


def _merge(runs: Inline) -> Inline:
    merged: Inline = []
    for run in runs:
        if merged and (merged[-1].bold, merged[-1].italic) == (run.bold, run.italic):
            merged[-1] = Run(
                text=merged[-1].text + run.text, bold=run.bold, italic=run.italic
            )
        elif run.text:
            merged.append(run)
    return merged


def html_to_content(html: str) -> ProseContent:
    """Parse editor HTML; raise ``ContentValidationError`` for unsupported markup."""
    reader = _Reader()
    reader.feed(html)
    reader.close()
    if reader.errors:
        raise ContentValidationError(reader.errors)
    # The editor adds empty paragraphs (e.g. after a list); they hold nothing,
    # and keeping them would make a click into the text a new revision.
    blocks = [
        block
        for block in reader.blocks
        if not isinstance(block, Paragraph) or plain_text(block.runs).strip()
    ]
    return ProseContent(blocks=blocks)


def editor_compatible(content: object) -> bool:
    """True when the rich text editor can show and save every block of ``content``."""
    return isinstance(content, ProseContent) and all(
        isinstance(block, Paragraph | Heading | BulletList | OrderedList)
        for block in content.blocks
    )


def _runs_html(runs: Inline) -> str:
    out = []
    for run in runs:
        text = escape(run.text)
        if run.bold:
            text = f"<strong>{text}</strong>"
        if run.italic:
            text = f"<em>{text}</em>"
        out.append(text)
    return "".join(out)


def _list_html(tag: str, items: list[Inline]) -> str:
    return (
        f"<{tag}>"
        + "".join(f"<li><p>{_runs_html(i)}</p></li>" for i in items)
        + f"</{tag}>"
    )


def _cells(tag: str, row: list[Inline]) -> str:
    return "<tr>" + "".join(f"<{tag}>{_runs_html(c)}</{tag}>" for c in row) + "</tr>"


def content_to_html(content: ProseContent) -> str:
    """Render the tree as editor HTML (also used for previews)."""
    parts: list[str] = []
    for block in content.blocks:
        if isinstance(block, Paragraph):
            parts.append(f"<p>{_runs_html(block.runs)}</p>")
        elif isinstance(block, Heading):
            parts.append(f"<h{block.level}>{_runs_html(block.runs)}</h{block.level}>")
        elif isinstance(block, BulletList):
            parts.append(_list_html("ul", block.items))
        elif isinstance(block, OrderedList):
            parts.append(_list_html("ol", block.items))
        elif isinstance(block, TableBlock):
            rows = "".join(_cells("td", row) for row in block.rows)
            parts.append(f"<table>{_cells('th', block.header)}{rows}</table>")
        else:
            label = escape(BOUND_FIELDS[block.field])
            parts.append(f'<p {BOUND_ATTR}="{block.field}">«{label}»</p>')
    return "".join(parts)
