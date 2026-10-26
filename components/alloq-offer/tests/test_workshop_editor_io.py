"""Round trip tests of the editor HTML converter (A06)."""

import pytest
from alloq_offer.workshop.content.editor_io import content_to_html, html_to_content
from alloq_offer.workshop.content.schema import (
    BoundValue,
    BulletList,
    ContentValidationError,
    Heading,
    OrderedList,
    Paragraph,
    ProseContent,
    Run,
    TableBlock,
)


def _roundtrip(content: ProseContent) -> ProseContent:
    return html_to_content(content_to_html(content))


def _same(a: ProseContent, b: ProseContent) -> bool:
    strip = {"block_id"}
    return [blk.model_dump(exclude=strip) for blk in a.blocks] == [
        blk.model_dump(exclude=strip) for blk in b.blocks
    ]


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
    assert content.blocks[2].items == [[Run(text="Punkt")]]
    text = "".join(r.text for r in content.blocks[1].runs)
    assert text == "Text mit fett und kursiv Zeile"


@pytest.mark.parametrize(
    ("html", "message"),
    [
        ("<h1>Zu groß</h1>", "Ebene 1"),
        ("<h2>Zu groß</h2>", "Ebene 2"),
        ('<p><a href="x">Link</a></p>', "Links"),
        ('<img src="x">', "Bilder"),
        ("<blockquote>Zitat</blockquote>", "Zitate"),
        ("<p><u>x</u></p>", "Unterstreichung"),
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
