"""Editor HTML <-> canonical content tree (A06).

The rich text editor emits HTML. Only the blocks of the content model are
accepted; anything else is reported, never dropped quietly. Images and tables
are chapter types of their own, never part of a text.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser

from alloq_offer.workshop.content.schema import (
    BOUND_FIELDS,
    EDITOR_BLOCKS,
    MAX_CELL,
    MAX_CODE,
    MAX_COLUMNS,
    MAX_LIST_DEPTH,
    MAX_TABLE_ROWS,
    TEXT_COLORS,
    BoundValue,
    BulletList,
    CodeBlock,
    ContentValidationError,
    Heading,
    Inline,
    ListItem,
    OrderedList,
    Paragraph,
    ProseContent,
    Quote,
    Rule,
    Run,
    TableBlock,
    TableContent,
    TaskList,
    plain_text,
    safe_link,
)

BOUND_ATTR = "data-bound"
MARK_TAGS = {
    "strong": "bold",
    "b": "bold",
    "em": "italic",
    "i": "italic",
    "u": "underline",
    "s": "strike",
    "del": "strike",
    "strike": "strike",
    "code": "code",
    "sub": "sub",
    "sup": "sup",
    "mark": "highlight",
}
MARKS = tuple(dict.fromkeys(MARK_TAGS.values()))
LIST_TAGS = {"ul", "ol"}
TABLE_PARTS = {"table", "thead", "tbody", "tr", "th", "td"}
HEADING_LEVELS = {"h3": 3, "h4": 4}
TEXT_CONTAINERS = {"p", "th", "td", *HEADING_LEVELS}
# Wrappers the editor puts around task items; they carry no content of their own.
NEUTRAL_TAGS = {"div", "span", "label", "input", "colgroup", "col"}
VOID_TAGS = {"img", "input", "col"}
UNSUPPORTED_NAMES = {
    "h1": "Überschrift Ebene 1",
    "h2": "Überschrift Ebene 2",
    "h5": "Überschrift Ebene 5",
    "h6": "Überschrift Ebene 6",
    "img": "Bilder (dafür gibt es den Kapiteltyp Bild)",
}
QUOTE_ONLY_TEXT = "Ein Zitat enthält nur Absätze."
NOT_NESTED = "Codeblöcke und Trennlinien stehen nicht in Listen oder Zitaten."
TOO_DEEP = f"Listen lassen sich höchstens {MAX_LIST_DEPTH} Ebenen tief schachteln."
ALIGN_STYLE = re.compile(r"text-align:\s*(left|center|right|justify)")
COLOR_STYLE = re.compile(r"(?<![-\w])color:\s*([^;]+)")
RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
LANGUAGE_CLASS = re.compile(r"language-([a-z0-9+#-]{1,30})")
COLOR_NAMES = {hex_.lower(): name for name, hex_ in TEXT_COLORS.items()}


def _color(style: str) -> str | None:
    """Palette name of a CSS color; colors outside the palette are not kept."""
    found = COLOR_STYLE.search(style)
    if found is None:
        return None
    value = found.group(1).strip().lower()
    rgb = RGB.match(value)
    if rgb is not None:
        value = "#" + "".join(f"{int(part):02x}" for part in rgb.groups())
    return COLOR_NAMES.get(value)


@dataclass
class _Item:
    runs: Inline = field(default_factory=list)
    checked: bool = False
    children: list[BulletList | OrderedList | TaskList] = field(default_factory=list)


@dataclass
class _ListFrame:
    kind: type[BulletList | OrderedList | TaskList]
    items: list[_Item] = field(default_factory=list)


@dataclass
class _QuoteFrame:
    paragraphs: list[Inline] = field(default_factory=list)


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list = []
        self.errors: list[str] = []
        self._runs: Inline = []
        self._marks = dict.fromkeys(MARKS, 0)
        self._links: list[str] = []
        self._colors: list[str | None] = []
        self._container = ""
        self._align = "left"
        self._bound = ""
        # Open lists, list items and quotes, innermost last.
        self._stack: list[_ListFrame | _Item | _QuoteFrame] = []
        self._code: list[str] | None = None
        self._language = ""
        self._table: list[list[Inline]] | None = None
        self._row: list[Inline] | None = None
        self._skip = 0
        self._inner_p = 0

    def _fail(self, message: str) -> None:
        if message not in self.errors:
            self.errors.append(message)

    def _top(self) -> _ListFrame | _Item | _QuoteFrame | None:
        return self._stack[-1] if self._stack else None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if self._code is not None:
            self._start_in_code(tag, values)
        elif tag in MARK_TAGS:
            self._marks[MARK_TAGS[tag]] += 1
        elif tag in self._starts:
            self._starts[tag](tag, values)
        elif tag in TEXT_CONTAINERS:
            self._open(tag, values)
        elif tag in UNSUPPORTED_NAMES:
            self._fail(f"Nicht erlaubt in Kapiteln: {UNSUPPORTED_NAMES[tag]}.")
            self._skip += tag not in VOID_TAGS
        elif tag not in TABLE_PARTS | NEUTRAL_TAGS:
            self._fail(f"Der Baustein „{tag}“ ist in Kapiteln nicht erlaubt.")

    @property
    def _starts(self) -> dict[str, Callable[[str, dict[str, str | None]], None]]:
        return {
            "a": lambda _, v: self._start_link(v.get("href") or ""),
            "span": lambda _, v: self._colors.append(_color(v.get("style") or "")),
            "ul": self._start_list,
            "ol": self._start_list,
            "li": lambda _, v: self._start_item(v),
            "blockquote": lambda *_: self._start_quote(),
            "pre": lambda *_: self._start_code(),
            "hr": lambda *_: self._add_block(Rule()),
            "table": lambda *_: setattr(self, "_table", []),
            "tr": lambda *_: setattr(self, "_row", []),
            "br": lambda *_: self._text(" "),
        }

    def _start_in_code(self, tag: str, values: dict[str, str | None]) -> None:
        if tag == "code":
            found = LANGUAGE_CLASS.search(values.get("class") or "")
            self._language = found.group(1) if found else ""
        elif tag == "br":
            self._code_text("\n")

    def _start_link(self, href: str) -> None:
        try:
            self._links.append(safe_link(href))
        except ValueError as exc:
            self._fail(str(exc))
            self._links.append("")

    def _start_list(self, tag: str, values: dict[str, str | None]) -> None:
        if isinstance(self._top(), _QuoteFrame):
            self._fail(QUOTE_ONLY_TEXT)
        if sum(isinstance(f, _ListFrame) for f in self._stack) >= MAX_LIST_DEPTH:
            self._fail(TOO_DEEP)
        self._flush_item()
        kind = OrderedList if tag == "ol" else BulletList
        if values.get("data-type") == "taskList":
            kind = TaskList
        self._stack.append(_ListFrame(kind))

    def _start_item(self, values: dict[str, str | None]) -> None:
        frame = self._top()
        if not isinstance(frame, _ListFrame):
            self._fail("Ein Listenpunkt steht außerhalb einer Liste.")
            return
        item = _Item(checked=values.get("data-checked") == "true")
        frame.items.append(item)
        self._stack.append(item)
        self._container, self._runs = "li", []

    def _start_quote(self) -> None:
        if self._stack:
            self._fail(QUOTE_ONLY_TEXT)
        self._stack.append(_QuoteFrame())

    def _start_code(self) -> None:
        if self._stack:
            self._fail(NOT_NESTED)
        self._code, self._language = [], ""

    def _open(self, tag: str, attrs: dict[str, str | None]) -> None:
        if self._container:
            self._inner_p += 1  # editors wrap list items and cells in <p>
            return
        self._container = tag
        self._runs = []
        style = ALIGN_STYLE.search(attrs.get("style") or "")
        self._align = style.group(1) if style else "left"
        self._bound = attrs.get(BOUND_ATTR) or "" if tag == "p" else ""

    def handle_endtag(self, tag: str) -> None:
        if self._code is not None:
            if tag == "pre":
                self._finish_code()
        elif tag in MARK_TAGS:
            self._marks[MARK_TAGS[tag]] = max(self._marks[MARK_TAGS[tag]] - 1, 0)
        elif tag in UNSUPPORTED_NAMES:
            self._skip = max(self._skip - (tag not in VOID_TAGS), 0)
        elif tag in {"p", *HEADING_LEVELS} and self._inner_p:
            self._inner_p -= 1
        elif tag in self._ends:
            self._ends[tag]()
        elif tag == self._container and tag in TEXT_CONTAINERS:
            self._close(tag)

    @property
    def _ends(self) -> dict[str, Callable[[], None]]:
        return {
            "a": lambda: self._links and self._links.pop() and None,
            "span": lambda: self._colors and self._colors.pop() and None,
            "li": self._finish_item,
            "ul": self._finish_list,
            "ol": self._finish_list,
            "blockquote": self._finish_quote,
            "tr": self._finish_row,
            "table": self._finish_table,
        }

    def _finish_row(self) -> None:
        if self._row is not None and self._table is not None:
            self._table.append(self._row)
        self._row = None

    def _flush_item(self) -> None:
        """Move the text read so far into the open list item."""
        item = self._top()
        if not isinstance(item, _Item) or self._container != "li":
            return
        runs = _merge(self._runs)
        if runs:
            item.runs = (
                _merge([*item.runs, Run(text=" "), *runs]) if item.runs else runs
            )
        self._runs, self._container = [], ""

    def _finish_item(self) -> None:
        self._flush_item()
        if isinstance(self._top(), _Item):
            self._stack.pop()

    def _finish_list(self) -> None:
        frame = self._top()
        if not isinstance(frame, _ListFrame):
            return
        self._stack.pop()
        block = frame.kind(
            items=[
                ListItem(runs=i.runs, checked=i.checked, children=i.children)
                for i in frame.items
            ]
        )
        parent = self._top()
        if isinstance(parent, _Item):
            parent.children.append(block)
            self._container, self._runs = "li", []  # text after the nested list
        elif not isinstance(parent, _QuoteFrame):
            self.blocks.append(block)

    def _finish_quote(self) -> None:
        frame = self._top()
        if isinstance(frame, _QuoteFrame):
            self._stack.pop()
            self.blocks.append(Quote(paragraphs=frame.paragraphs))

    def _finish_code(self) -> None:
        text, self._code = "".join(self._code or []), None
        if len(text) > MAX_CODE:
            self._fail("Ein Codeblock ist zu lang.")
            return
        self._add_block(
            CodeBlock(text=text.removesuffix("\n"), language=self._language)
        )

    def _add_block(self, block: object) -> None:
        if self._stack:
            self._fail(NOT_NESTED)
            return
        self.blocks.append(block)

    def _close(self, tag: str) -> None:
        runs, self._runs, self._container = _merge(self._runs), [], ""
        frame = self._top()
        if tag in {"th", "td"} and self._row is not None:
            self._row.append(runs)
        elif isinstance(frame, _QuoteFrame):
            if tag != "p" or self._bound:
                self._fail(QUOTE_ONLY_TEXT)
            frame.paragraphs.append(runs)
        elif tag in HEADING_LEVELS:
            self.blocks.append(
                Heading(level=HEADING_LEVELS[tag], runs=runs, align=self._align)
            )
        elif tag == "p":
            if self._bound:
                self._add_bound()
            else:
                self.blocks.append(Paragraph(runs=runs, align=self._align))

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
                    **{mark: bool(count) for mark, count in self._marks.items()},
                    color=next((c for c in reversed(self._colors) if c), None),
                    link=self._links[-1] if self._links else "",
                )
            )

    def _code_text(self, data: str) -> None:
        if self._code is not None:
            self._code.append(data)

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._code is not None:
            self._code_text(data)
            return
        if data.strip() and not self._container:
            self._fail("Text außerhalb eines Absatzes ist nicht erlaubt.")
        self._text(data)


def _style(run: Run) -> dict:
    return run.model_dump(exclude={"text"})


def _merge(runs: Inline) -> Inline:
    merged: Inline = []
    for run in runs:
        if merged and _style(merged[-1]) == _style(run):
            merged[-1] = merged[-1].model_copy(
                update={"text": merged[-1].text + run.text}
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
        isinstance(block, EDITOR_BLOCKS) for block in content.blocks
    )


def _run_html(run: Run) -> str:
    text = escape(run.text)
    for mark, tag in (
        ("code", "code"),
        ("sub", "sub"),
        ("sup", "sup"),
        ("strike", "s"),
        ("underline", "u"),
        ("italic", "em"),
        ("bold", "strong"),
        ("highlight", "mark"),
    ):
        if getattr(run, mark):
            text = f"<{tag}>{text}</{tag}>"
    if run.color:
        text = f'<span style="color: {TEXT_COLORS[run.color]}">{text}</span>'
    if run.link:
        text = f'<a href="{escape(run.link, quote=True)}">{text}</a>'
    return text


def _runs_html(runs: Inline) -> str:
    return "".join(_run_html(run) for run in runs)


def _align_attr(align: str) -> str:
    return "" if align == "left" else f' style="text-align: {align}"'


def _list_html(block: BulletList | OrderedList | TaskList) -> str:
    items = []
    for item in block.items:
        children = "".join(_list_html(child) for child in item.children)
        task = ""
        if isinstance(block, TaskList):
            task = f' data-type="taskItem" data-checked="{str(item.checked).lower()}"'
        items.append(f"<li{task}><p>{_runs_html(item.runs)}</p>{children}</li>")
    if isinstance(block, TaskList):
        return f'<ul data-type="taskList">{"".join(items)}</ul>'
    tag = "ol" if isinstance(block, OrderedList) else "ul"
    return f"<{tag}>{''.join(items)}</{tag}>"


def _cells(tag: str, row: list[Inline]) -> str:
    return "<tr>" + "".join(f"<{tag}>{_runs_html(c)}</{tag}>" for c in row) + "</tr>"


def _quote_html(block: Quote) -> str:
    inner = "".join(f"<p>{_runs_html(p)}</p>" for p in block.paragraphs)
    return f"<blockquote>{inner}</blockquote>"


def _code_html(block: CodeBlock) -> str:
    language = f' class="language-{block.language}"' if block.language else ""
    return f"<pre><code{language}>{escape(block.text)}</code></pre>"


def _heading_html(block: Heading) -> str:
    tag = f"h{block.level}"
    return f"<{tag}{_align_attr(block.align)}>{_runs_html(block.runs)}</{tag}>"


def _table_html(block: TableBlock) -> str:
    rows = "".join(_cells("td", row) for row in block.rows)
    return f"<table>{_cells('th', block.header)}{rows}</table>"


def _bound_html(block: BoundValue) -> str:
    label = escape(BOUND_FIELDS[block.field])
    return f'<p {BOUND_ATTR}="{block.field}">«{label}»</p>'


BLOCK_HTML: dict[type, Callable] = {
    Paragraph: lambda b: f"<p{_align_attr(b.align)}>{_runs_html(b.runs)}</p>",
    Heading: _heading_html,
    BulletList: _list_html,
    OrderedList: _list_html,
    TaskList: _list_html,
    Quote: _quote_html,
    CodeBlock: _code_html,
    Rule: lambda _: "<hr>",
    TableBlock: _table_html,
    BoundValue: _bound_html,
}


def content_to_html(content: ProseContent) -> str:
    """Render the tree as editor HTML (also used for previews)."""
    return "".join(BLOCK_HTML[type(block)](block) for block in content.blocks)


ONE_TABLE = "Ein Tabellenkapitel enthält genau eine Tabelle."
TOO_WIDE = f"Eine Tabelle hat höchstens {MAX_COLUMNS} Spalten."
TOO_LONG = f"Eine Tabelle hat höchstens {MAX_TABLE_ROWS} Zeilen."
CELL_TOO_LONG = f"Eine Zelle hat höchstens {MAX_CELL} Zeichen."
PLAIN_HEADER = "Die Kopfzeile einer Tabelle ist reiner Text, ohne Formatierung."


def html_to_table(html: str, description: Inline) -> TableContent:
    """Parse the table editor's HTML; the header row gives the column names."""
    blocks = [
        b
        for b in html_to_content(html).blocks
        if not isinstance(b, Paragraph) or plain_text(b.runs).strip()
    ]
    if len(blocks) != 1 or not isinstance(blocks[0], TableBlock):
        raise ContentValidationError([ONE_TABLE])
    table = blocks[0]
    errors = []
    if len(table.header) > MAX_COLUMNS:
        errors.append(TOO_WIDE)
    if len(table.rows) > MAX_TABLE_ROWS:
        errors.append(TOO_LONG)
    cells = [table.header, *table.rows]
    if any(len(plain_text(cell)) > MAX_CELL for row in cells for cell in row):
        errors.append(CELL_TOO_LONG)
    plain = Run(text="").model_dump(exclude={"text"})
    if any(_style(run) != plain for cell in table.header for run in cell):
        errors.append(PLAIN_HEADER)
    if errors:
        raise ContentValidationError(errors)
    return TableContent(
        columns=[plain_text(cell).strip() for cell in table.header],
        rows=table.rows,
        description=description,
    )


def table_to_html(content: TableContent) -> str:
    """The table editor's HTML of a table chapter; the header row is plain text."""
    header = "".join(f"<th><p>{escape(c)}</p></th>" for c in content.columns)
    rows = "".join(
        "<tr>" + "".join(f"<td><p>{_runs_html(c)}</p></td>" for c in row) + "</tr>"
        for row in content.rows
    )
    return f"<table><tbody><tr>{header}</tr>{rows}</tbody></table>"
