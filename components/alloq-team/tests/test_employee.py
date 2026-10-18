"""Tests for employee components."""

from alloq_team.components.employee import absence_modal, employee_form_fields


def test_absence_picker_allows_a_single_day_range() -> None:
    rendered = str(absence_modal().render())

    assert "allowSingleDateInRange:true" in rendered


def test_employee_text_inputs_limit_length_in_browser() -> None:
    rendered = str(employee_form_fields())

    assert rendered.count("maxLength:255") == 5
    assert '["maxLength"]' not in rendered
