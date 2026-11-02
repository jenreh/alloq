import pytest
from alloq_offer.workshop.content.schema import (
    CalcContent,
    ContentValidationError,
    ProseContent,
    StoriesContent,
    parse_content,
)


def _run(text: str) -> dict:
    return {"text": text}


def test_prose_roundtrip_keeps_block_ids() -> None:
    raw = {
        "chapter_type": "prose",
        "blocks": [
            {"type": "paragraph", "block_id": "a1", "runs": [_run("Hallo")]},
            {"type": "bullet_list", "items": [[_run("eins")], [_run("zwei")]]},
        ],
    }
    content = parse_content(raw)
    assert isinstance(content, ProseContent)
    assert content.blocks[0].block_id == "a1"
    assert content.blocks[1].block_id
    assert parse_content(content.model_dump()) == content


def test_unknown_chapter_type_rejected() -> None:
    with pytest.raises(ContentValidationError) as exc:
        parse_content({"chapter_type": "map"})
    assert exc.value.messages == ["Unbekannter Kapiteltyp."]


def test_unsupported_block_rejected_with_german_message() -> None:
    raw = {"chapter_type": "prose", "blocks": [{"type": "image", "src": "x"}]}
    with pytest.raises(ContentValidationError) as exc:
        parse_content(raw)
    assert "Nicht unterstützter Inhaltsbaustein" in exc.value.messages[0]


def test_heading_levels_limited() -> None:
    raw = {"chapter_type": "prose", "blocks": [{"type": "heading", "level": 1}]}
    with pytest.raises(ContentValidationError):
        parse_content(raw)


def test_table_rows_must_match_header() -> None:
    raw = {
        "chapter_type": "prose",
        "blocks": [
            {
                "type": "table",
                "header": [[_run("A")], [_run("B")]],
                "rows": [[[_run("x")]]],
            }
        ],
    }
    with pytest.raises(ContentValidationError) as exc:
        parse_content(raw)
    assert "Zellen" in exc.value.messages[0]


def test_table_chapter_needs_columns_and_matching_rows() -> None:
    with pytest.raises(ContentValidationError):
        parse_content({"chapter_type": "table", "columns": []})
    with pytest.raises(ContentValidationError):
        parse_content(
            {
                "chapter_type": "table",
                "columns": ["A"],
                "rows": [[[_run("x")], [_run("y")]]],
            }
        )


def test_bound_value_must_be_known_field() -> None:
    raw = {"chapter_type": "prose", "blocks": [{"type": "bound_value", "field": "x.y"}]}
    with pytest.raises(ContentValidationError) as exc:
        parse_content(raw)
    assert "Unbekannter Kalkulationswert" in exc.value.messages[0]


def test_stories_holds_only_settings() -> None:
    content = parse_content({"chapter_type": "stories"})
    assert isinstance(content, StoriesContent)
    assert content.group_by == "activity"
    # Content stored while stories still had a scope stays readable.
    old = parse_content({"chapter_type": "stories", "scopes": ["angeboten"]})
    assert old == StoriesContent()
    with pytest.raises(ContentValidationError):
        parse_content({"chapter_type": "stories", "group_by": "rolle"})


def test_calc_rows_use_bound_fields() -> None:
    content = parse_content(
        {
            "chapter_type": "calc",
            "rows": [{"label": "Preis", "field": "offer.recommended_price"}],
        }
    )
    assert isinstance(content, CalcContent)
    assert content.rows[0].field == "offer.recommended_price"
    with pytest.raises(ContentValidationError):
        parse_content(
            {"chapter_type": "calc", "rows": [{"label": "X", "field": "offer.secret"}]}
        )
