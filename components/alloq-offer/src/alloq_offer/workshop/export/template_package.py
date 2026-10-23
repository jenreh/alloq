"""Template package: chapter catalogue, rules and Word layout of one template."""

from __future__ import annotations

import io
from functools import cache, cached_property
from pathlib import Path
from typing import Any, Literal

import yaml
from docx import Document
from docx.document import Document as DocxDocument
from docx.text.paragraph import Paragraph as DocxParagraph
from pydantic import BaseModel, Field, model_validator

TEMPLATES_ROOT = Path(__file__).resolve().parent.parent / "templates"
DEFAULT_TEMPLATE_KEY = "quo_v1"
CHAPTER_ANCHOR = "[[KAPITEL]]"


class TemplateError(ValueError):
    """The template package is inconsistent."""


class ChapterDef(BaseModel):
    key: str
    title: str
    level: Literal[1, 2] = 1
    required: bool = False
    chapter_type: Literal["prose", "table", "stories", "calc"]
    defaults: dict[str, Any] = Field(default_factory=dict)
    guiding_question: str = ""
    content_rules: list[str] = Field(default_factory=list)


class TemplatePackage(BaseModel):
    key: str
    version: str
    chapters: list[ChapterDef]
    static_chapters: list[str] = Field(default_factory=list)
    rules: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    layout_path: Path

    @model_validator(mode="after")
    def _unique_keys(self) -> TemplatePackage:
        keys = [chapter.key for chapter in self.chapters]
        if len(keys) != len(set(keys)):
            raise TemplateError("Kapitelschlüssel müssen eindeutig sein.")
        return self

    def chapter(self, key: str) -> ChapterDef:
        for chapter in self.chapters:
            if chapter.key == key:
                return chapter
        raise KeyError(key)

    @cached_property
    def layout_bytes(self) -> bytes:
        return self.layout_path.read_bytes()

    def check_layout(self) -> None:
        """Fail unless the layout holds the chapter anchor exactly once."""
        document = Document(io.BytesIO(self.layout_bytes))
        anchors = [p for p in document.paragraphs if p.text.strip() == CHAPTER_ANCHOR]
        if len(anchors) != 1:
            raise TemplateError(
                f"Die Vorlage braucht genau einen Anker {CHAPTER_ANCHOR}."
            )


def find_anchor(document: DocxDocument) -> DocxParagraph:
    for paragraph in document.paragraphs:
        if paragraph.text.strip() == CHAPTER_ANCHOR:
            return paragraph
    raise TemplateError(f"Die Vorlage braucht genau einen Anker {CHAPTER_ANCHOR}.")


@cache
def load_template(
    key: str = DEFAULT_TEMPLATE_KEY, root: Path = TEMPLATES_ROOT
) -> TemplatePackage:
    base = root / key
    chapters_doc = yaml.safe_load((base / "chapters.yaml").read_text(encoding="utf-8"))
    rules_doc = yaml.safe_load((base / "rules.yaml").read_text(encoding="utf-8"))
    package = TemplatePackage(
        key=key,
        version=chapters_doc["version"],
        chapters=[ChapterDef(**item) for item in chapters_doc["chapters"]],
        static_chapters=chapters_doc.get("static_chapters", []),
        rules=rules_doc.get("chapters", {}),
        layout_path=base / "layout.docx",
    )
    package.check_layout()
    return package
