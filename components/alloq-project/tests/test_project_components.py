"""Render checks for project drawer/form components (compiled props & events)."""

import json
import re

from alloq_commons.models.project import Project
from alloq_project.components.project_card import project_card
from alloq_project.components.project_form import project_form_fields
from alloq_project.components.project_risk_tab import risiken_tab
from alloq_project.components.project_status_tab import status_tab
from alloq_project.states.project_state import ProjectState

_BOUND = r'{event}:\(\(_e\) => \(addEvents\(\[\(ReflexEvent\("[^"]*\.'


def _handler_payload(rendered: str, handler: str) -> str:
    """The compiled event payload following a ReflexEvent for *handler*."""
    match = re.search(re.escape(handler) + r'", \(\{(.*?)\}\)', rendered)
    assert match, f"{handler} not bound"
    return match.group(1)


def _contains_text(rendered: str, text: str) -> bool:
    """Match plain or JSON-escaped (non-ASCII) string literals."""
    return text in rendered or json.dumps(text)[1:-1] in rendered


class TestProjectForm:
    def test_inputs_sync_on_blur_not_on_change(self) -> None:
        rendered = str(project_form_fields())

        for handler in (
            "set_name_de",
            "set_code",
            "set_customer",
            "set_budget",
            "set_role_capacity",
        ):
            assert re.search(_BOUND.format(event="onBlur") + handler, rendered)
            assert not re.search(_BOUND.format(event="onChange") + handler, rendered)

    def test_budget_allows_two_decimals(self) -> None:
        rendered = str(project_form_fields())

        assert re.search(r"decimalScale:\s*2", rendered)

    def test_customer_has_no_error_binding(self) -> None:
        rendered = str(project_form_fields())

        assert "customer_error" not in rendered

    def test_budget_decimal_scale_is_a_prop_not_css(self) -> None:
        rendered = str(project_form_fields())

        assert '["decimalScale"]' not in rendered

    def test_has_internal_project_switch(self) -> None:
        rendered = str(project_form_fields())

        assert _contains_text(rendered, "Internes Projekt")
        assert _contains_text(rendered, "is_internal")

    def test_has_booking_number_input_synced_on_blur(self) -> None:
        rendered = str(project_form_fields())

        assert _contains_text(rendered, "booking_number")
        assert re.search(_BOUND.format(event="onBlur") + "set_booking_number", rendered)


class TestProjectCard:
    def test_nowrap_is_not_emitted_as_css(self) -> None:
        rendered = str(project_card(ProjectState.projects[0].to(Project)))

        assert '["nowrap"]' not in rendered

    def test_card_caps_team_avatars(self) -> None:
        rendered = str(project_card(ProjectState.projects[0].to(Project)))

        assert re.search(r'\["team_members"\][^,]*slice', rendered)


class TestStatusTab:
    def test_status_delete_requires_confirmation(self) -> None:
        rendered = str(status_tab())

        assert _contains_text(rendered, "Status löschen")

    def test_add_status_sends_rendered_form_version(self) -> None:
        rendered = str(status_tab())

        assert "status_form_version" in _handler_payload(rendered, "add_project_status")

    def test_date_column_does_not_shrink(self) -> None:
        rendered = str(status_tab())

        assert "flexShrinkg" not in rendered


class TestRiskTab:
    def test_risk_delete_requires_confirmation(self) -> None:
        rendered = str(risiken_tab())

        assert _contains_text(rendered, "Risiko löschen")

    def test_risk_edit_form_is_keyed_by_draft_version(self) -> None:
        rendered = str(risiken_tab())

        assert "risk_draft_form_version" in rendered
