"""Rendering checks for the planning toolbar."""

from alloq_project.components.planning_toolbar import planning_toolbar


def test_section_toggle_icon_tracks_collapsed_state() -> None:
    rendered = str(planning_toolbar()[0])

    assert "chevrons-up" in rendered
    assert "chevrons-down" in rendered
    assert "all_sections_collapsed" in rendered
