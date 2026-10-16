"""Tests for employee components."""

from alloq_team.components.employee import absence_modal


def test_absence_picker_allows_a_single_day_range() -> None:
    rendered = str(absence_modal().render())

    assert "allowSingleDateInRange:true" in rendered
