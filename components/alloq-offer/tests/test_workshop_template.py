from pathlib import Path

import pytest
from alloq_offer.workshop.content.schema import parse_content
from alloq_offer.workshop.export.template_package import (
    CHAPTER_ANCHOR,
    TemplateError,
    TemplatePackage,
    load_template,
)
from docx import Document
from pydantic import ValidationError


def test_default_template_loads() -> None:
    package = load_template()
    assert package.version.startswith("quo_v1")
    keys = [c.key for c in package.chapters]
    assert keys[0] == "management_summary"
    assert "story_map" not in keys
    assert {c.chapter_type for c in package.chapters} == {
        "prose",
        "table",
        "stories",
        "calc",
    }


def test_chapter_defaults_are_valid_content() -> None:
    package = load_template()
    stories = package.chapter("user_stories")
    parse_content({"chapter_type": "stories", **stories.defaults})
    calc = package.chapter("verguetung")
    parse_content({"chapter_type": "calc", **calc.defaults})
    table = package.chapter("mitwirkung")
    parse_content({"chapter_type": "table", "columns": table.defaults["columns"]})


def test_layout_has_single_anchor_and_no_customer_data() -> None:
    package = load_template()
    package.check_layout()
    text = "\n".join(p.text for p in Document(str(package.layout_path)).paragraphs)
    assert text.count(CHAPTER_ANCHOR) == 1
    assert "TREYSTA" not in text
    assert "Treysta" not in text


def test_duplicate_chapter_keys_rejected() -> None:
    package = load_template()
    chapter = package.chapters[0].model_dump()
    with pytest.raises(ValidationError, match="eindeutig"):
        TemplatePackage(
            key="x",
            version="1",
            chapters=[chapter, chapter],
            layout_path=package.layout_path,
        )


def test_layout_without_anchor_rejected(tmp_path: Path) -> None:
    layout = tmp_path / "layout.docx"
    Document().save(str(layout))
    package = TemplatePackage(key="x", version="1", chapters=[], layout_path=layout)
    with pytest.raises(TemplateError):
        package.check_layout()
