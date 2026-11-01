"""Stories chapters filtered by column (activity) and slice."""

from alloq_offer.workshop.content.schema import StoriesContent, parse_content
from alloq_offer.workshop.export.models import (
    ResolvedStory,
    filter_label,
    filter_stories,
    story_filter_options,
)

STORIES = [
    ResolvedStory("US-01", "A", "s", "Erfassen", "MVP", 0, 1, 10),
    ResolvedStory("US-02", "B", "s", "Erfassen", "", 0, 1, 0),
    ResolvedStory("US-03", "C", "s", "Abrechnen", "MVP", 0, 2, 10),
    ResolvedStory("US-04", "D", "s", "Abrechnen", "Später", 1, 2, 11),
]


def _keys(content: StoriesContent) -> list[str]:
    return [s.key for s in filter_stories(STORIES, content)]


def test_no_filter_keeps_every_story() -> None:
    assert _keys(StoriesContent()) == ["US-01", "US-02", "US-03", "US-04"]


def test_filter_by_column_slice_both_and_unsliced() -> None:
    assert _keys(StoriesContent(activity_ids=[2])) == ["US-03", "US-04"]
    assert _keys(StoriesContent(slice_ids=[10])) == ["US-01", "US-03"]
    assert _keys(StoriesContent(activity_ids=[2], slice_ids=[11])) == ["US-04"]
    assert _keys(StoriesContent(unsliced=True)) == ["US-02"]
    assert _keys(StoriesContent(slice_ids=[11], unsliced=True)) == ["US-02", "US-04"]
    assert _keys(StoriesContent(activity_ids=[99])) == []


def test_old_stored_content_has_no_filter() -> None:
    content = parse_content({"chapter_type": "stories", "group_by": "slice"})
    assert isinstance(content, StoriesContent)
    assert content.activity_ids == content.slice_ids == []
    assert not content.unsliced


def test_options_count_the_stories_and_label_the_filter() -> None:
    options = story_filter_options(STORIES)
    assert options["activities"] == [
        {"value": "1", "label": "Erfassen (2)"},
        {"value": "2", "label": "Abrechnen (2)"},
    ]
    assert options["slices"] == [
        {"value": "10", "label": "MVP (2)"},
        {"value": "11", "label": "Später (1)"},
        {"value": "none", "label": "Ohne Schnitt (1)"},
    ]
    content = StoriesContent(activity_ids=[2], slice_ids=[10], unsliced=True)
    assert filter_label(STORIES, content) == (
        "Spalten: Abrechnen · Schnitte: MVP, Ohne Schnitt"
    )
    assert filter_label(STORIES, StoriesContent()) == ""
