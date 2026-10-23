"""What the model may propose; validated before anything is stored."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from alloq_offer.workshop.content.schema import (
    BulletList,
    Heading,
    OrderedList,
    Paragraph,
    ProseContent,
)
from alloq_offer.workshop.entities import StatementType


class ProposedStory(BaseModel):
    """A story as the model wrote it; the format is checked when it is stored."""

    title: str
    role: str = Field(description="Role without the leading 'Als'")
    goal: str = Field(description="What the role wants to do, after 'möchte ich'")
    benefit: str = Field(description="Why, after 'um'")
    origin: Literal["Kunde", "Vorschlag"] = "Vorschlag"
    source_refs: list[int] = Field(default_factory=list)
    skeleton: bool = False
    slice: str | None = None


class ProposedTask(BaseModel):
    title: str
    stories: list[ProposedStory] = Field(default_factory=list)


class ProposedActivity(BaseModel):
    title: str
    tasks: list[ProposedTask] = Field(default_factory=list)


class ProposedPoint(BaseModel):
    """An open question or a conflict between sources."""

    text: str
    source_refs: list[int] = Field(default_factory=list)


class ProposedMap(BaseModel):
    vision: str = ""
    roles: list[str] = Field(default_factory=list)
    activities: list[ProposedActivity] = Field(default_factory=list)
    slices: list[str] = Field(default_factory=list)
    open_questions: list[ProposedPoint] = Field(default_factory=list)
    conflicts: list[ProposedPoint] = Field(default_factory=list)


class ProposedStatement(BaseModel):
    type: StatementType
    text: str
    source_refs: list[int] = Field(default_factory=list)


class ProposedBriefing(BaseModel):
    statements: list[ProposedStatement] = Field(default_factory=list)


EditorBlock = Annotated[
    Paragraph | Heading | BulletList | OrderedList, Field(discriminator="type")
]


class ProposedChapter(BaseModel):
    """Chapter text in the blocks the editor can show; no tables or bound values."""

    blocks: list[EditorBlock] = Field(default_factory=list)

    def to_content(self) -> ProseContent:
        return ProseContent(blocks=list(self.blocks))
