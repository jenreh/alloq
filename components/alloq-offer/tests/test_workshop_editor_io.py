"""Round trip tests of the editor HTML converter (A06)."""

import pytest
from alloq_offer.workshop.content.editor_io import (
    content_to_html,
    editor_compatible,
    html_to_content,
    html_to_table,
    table_to_html,
)
from alloq_offer.workshop.content.schema import (
    BoundValue,
    BulletList,
    CodeBlock,
    ContentValidationError,
    Heading,
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
    parse_content,
)


def _roundtrip(content: ProseContent) -> ProseContent:
    return html_to_content(content_to_html(content))


def _without_ids(value: object) -> object:
    if isinstance(value, dict):
        return {k: _without_ids(v) for k, v in value.items() if k != "block_id"}
    if isinstance(value, list):
        return [_without_ids(v) for v in value]
    return value


def _same(a: ProseContent, b: ProseContent) -> bool:
    return _without_ids(a.model_dump()) == _without_ids(b.model_dump())


def test_paragraph_with_marks_survives() -> None:
    content = ProseContent(
        blocks=[
            Paragraph(
                runs=[
                    Run(text="Wir "),
                    Run(text="liefern", bold=True),
                    Run(text=" und ", italic=True),
                    Run(text="mehr", bold=True, italic=True),
                ]
            )
        ]
    )
    assert _same(_roundtrip(content), content)


def test_headings_lists_tables_and_bound_values_survive() -> None:
    cell = [Run(text="A & B <1>")]
    content = ProseContent(
        blocks=[
            Heading(level=3, runs=[Run(text="Ziel")]),
            Heading(level=4, runs=[Run(text="Detail")]),
            BulletList(items=[[Run(text="eins")], [Run(text="zwei", bold=True)]]),
            OrderedList(items=[[Run(text="erst")], [Run(text="dann")]]),
            TableBlock(
                header=[[Run(text="Rolle")], [Run(text="Aufgabe")]], rows=[[cell, cell]]
            ),
            BoundValue(field="offer.recommended_price"),
            Paragraph(runs=[Run(text="Schluss")]),
        ]
    )
    html = content_to_html(content)
    assert "&amp; B &lt;1&gt;" in html
    assert 'data-bound="offer.recommended_price"' in html
    assert _same(_roundtrip(content), content)


def test_editor_style_html_is_read() -> None:
    html = (
        "<h3>Titel</h3><p>Text mit <b>fett</b> und <i>kursiv</i><br>Zeile</p>"
        "<ul><li><p>Punkt</p></li></ul>"
    )
    content = html_to_content(html)
    assert [type(b) for b in content.blocks] == [Heading, Paragraph, BulletList]
    assert content.blocks[2].items == [ListItem(runs=[Run(text="Punkt")])]
    text = "".join(r.text for r in content.blocks[1].runs)
    assert text == "Text mit fett und kursiv Zeile"


@pytest.mark.parametrize(
    ("html", "message"),
    [
        ("<h1>Zu groß</h1>", "Ebene 1"),
        ("<h2>Zu groß</h2>", "Ebene 2"),
        ('<p><a href="x">Link</a></p>', "http"),
        ('<p><a href="javascript:alert(1)">Link</a></p>', "http"),
        ('<img src="x">', "Bilder"),
        ("<blockquote>Zitat</blockquote>", "außerhalb"),
        ("<blockquote><ul><li>x</li></ul></blockquote>", "Zitat"),
        ("<ul><li><pre>x</pre></li></ul>", "Codeblöcke"),
        ("<ul><li>" * 7 + "x" + "</li></ul>" * 7, "Ebenen"),
        ("<video></video>", "„video“"),
        ("Text ohne Absatz", "außerhalb"),
        ('<p data-bound="offer.nope">x</p>', "Unbekannter Kalkulationswert"),
        (
            "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td></tr></table>",
            "gleich viele",
        ),
        ("<table></table>", "Kopfzeile"),
    ],
)
def test_unsupported_markup_is_reported_not_dropped(html: str, message: str) -> None:
    with pytest.raises(ContentValidationError, match=message):
        html_to_content(html)


def test_every_problem_is_listed_once() -> None:
    with pytest.raises(ContentValidationError) as caught:
        html_to_content("<h1>a</h1><h1>b</h1><img>")
    assert len(caught.value.messages) == 2


def test_empty_html_is_an_empty_document() -> None:
    assert html_to_content("").blocks == []
    assert content_to_html(ProseContent()) == ""


def test_empty_paragraphs_are_dropped() -> None:
    content = html_to_content(
        "<p>Text</p><ul><li><p>Punkt</p></li></ul><p></p><p> </p>"
    )
    assert [block.type for block in content.blocks] == ["paragraph", "bullet_list"]


def test_every_text_format_survives() -> None:
    content = ProseContent(
        blocks=[
            Paragraph(
                align="center",
                runs=[
                    Run(text="unter", underline=True),
                    Run(text="durch", strike=True),
                    Run(text="code", code=True),
                    Run(text="2", sub=True),
                    Run(text="3", sup=True),
                    Run(text="gelb", highlight=True),
                    Run(text="rot", color="red", bold=True),
                    Run(text="Seite", link="https://example.com/?a=1&b=2"),
                ],
            ),
            Heading(level=4, align="right", runs=[Run(text="Rechts")]),
            Quote(paragraphs=[[Run(text="Zitat")], [Run(text="zwei", italic=True)]]),
            CodeBlock(text="if a < b:\n    pass", language="python"),
            Rule(),
            TaskList(
                items=[
                    ListItem(runs=[Run(text="offen")]),
                    ListItem(runs=[Run(text="fertig")], checked=True),
                ]
            ),
        ]
    )
    assert _same(_roundtrip(content), content)
    assert editor_compatible(content)


def test_nested_lists_survive() -> None:
    inner = OrderedList(items=[ListItem(runs=[Run(text="b1")])])
    deeper = BulletList(items=[ListItem(runs=[Run(text="c")])])
    middle = BulletList(items=[ListItem(runs=[Run(text="x")], children=[deeper])])
    content = ProseContent(
        blocks=[
            BulletList(
                items=[
                    ListItem(runs=[Run(text="a")], children=[inner]),
                    ListItem(
                        runs=[Run(text="b")],
                        children=[middle],
                    ),
                ]
            )
        ]
    )
    assert _same(_roundtrip(content), content)


def test_tiptap_task_items_and_colors_are_read() -> None:
    html = (
        '<ul data-type="taskList"><li data-checked="true" data-type="taskItem">'
        '<label><input type="checkbox" checked="checked"><span></span></label>'
        "<div><p>Erledigt</p></div></li></ul>"
        '<p><span style="color: rgb(215, 0, 21)">rot</span>'
        '<span style="color: #123456">fremd</span>'
        '<a target="_blank" rel="noopener" href="mailto:a@b.de">Mail</a></p>'
        '<pre><code class="language-sql">select 1;\nselect 2;</code></pre>'
    )
    content = html_to_content(html)
    task, paragraph, code = content.blocks
    assert isinstance(task, TaskList)
    assert task.items[0].checked
    assert task.items[0].runs[0].text == "Erledigt"
    assert [(r.text, r.color, r.link) for r in paragraph.runs] == [
        ("rot", "red", ""),
        ("fremd", None, ""),
        ("Mail", None, "mailto:a@b.de"),
    ]
    assert (code.text, code.language) == ("select 1;\nselect 2;", "sql")


def test_text_after_a_nested_list_stays_in_the_item() -> None:
    content = html_to_content("<ul><li>a<ul><li>b</li></ul>c</li></ul>")
    [item] = content.blocks[0].items
    assert item.runs[0].text == "a c"
    assert item.children[0].items[0].runs[0].text == "b"


def test_stored_lists_from_before_nesting_still_load() -> None:
    content = parse_content(
        {
            "chapter_type": "prose",
            "blocks": [{"type": "bullet_list", "items": [[{"text": "alt"}]]}],
        }
    )
    assert content.blocks[0].items[0].runs[0].text == "alt"
    with pytest.raises(ContentValidationError, match="http"):
        parse_content(
            {
                "chapter_type": "prose",
                "blocks": [
                    {
                        "type": "paragraph",
                        "runs": [{"text": "x", "link": "javascript:alert(1)"}],
                    }
                ],
            }
        )


def test_table_chapters_round_trip_through_the_table_editor() -> None:
    content = TableContent(
        columns=["Rolle", "Aufgabe"],
        rows=[[[Run(text="Kunde", bold=True)], [Run(text="Zugang & Daten")]]],
        description=[Run(text="Pflichten")],
    )
    html = table_to_html(content)
    assert "<th><p>Rolle</p></th>" in html
    back = html_to_table(html, content.description)
    assert back == content


def test_tiptap_table_html_is_read() -> None:
    html = (
        '<table style="min-width: 50px"><colgroup><col><col></colgroup><tbody>'
        '<tr><th colspan="1" rowspan="1"><p>A</p></th>'
        '<th colspan="1" rowspan="1"><p>B</p></th></tr>'
        '<tr><td colspan="1" rowspan="1"><p><em>1</em></p></td>'
        '<td colspan="1" rowspan="1"><p></p></td></tr></tbody></table>'
    )
    table = html_to_table(html, [])
    assert table.columns == ["A", "B"]
    assert table.rows == [[[Run(text="1", italic=True)], []]]


@pytest.mark.parametrize(
    ("html", "message"),
    [
        ("<p>kein</p>", "genau eine Tabelle"),
        ("<table><tr><th>A</th></tr></table>" * 2, "genau eine Tabelle"),
        ("<table><tr><th>A</th><th>B</th></tr><tr><td>1</td></tr></table>", "Zellen"),
        ("<table><tr>" + "<th>x</th>" * 9 + "</tr></table>", "Spalten"),
        ("<table><tr><th><strong>A</strong></th></tr></table>", "Kopfzeile"),
        (
            "<table><tr><th>A</th></tr><tr><td>" + "x" * 2001 + "</td></tr></table>",
            "Zeichen",
        ),
        (
            "<table><tr><th>A</th></tr>" + "<tr><td>x</td></tr>" * 201 + "</table>",
            "Zeilen",
        ),
    ],
)
def test_bad_tables_are_refused(html: str, message: str) -> None:
    with pytest.raises(ContentValidationError, match=message):
        html_to_table(html, [])
