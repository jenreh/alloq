"""Render checks for project drawer/form components (compiled props & events)."""

import json
import re

from alloq_commons.models.project import Project
from alloq_project.components.project_card import project_card
from alloq_project.components.project_form import project_form_fields
from alloq_project.components.project_risk_tab import risiken_tab
from alloq_project.components.project_status_tab import status_tab
from alloq_project.states.project_state import ProjectState


def _handler_payload(rendered: str, handler: str) -> str:
    """The compiled event payload following a ReflexEvent for *handler*."""
    match = re.search(re.escape(handler) + r'", \(\{(.*?)\}\)', rendered)
    assert match, f"{handler} not bound"
    return match.group(1)


def _contains_text(rendered: str, text: str) -> bool:
    """Match plain or JSON-escaped (non-ASCII) string literals."""
    return text in rendered or json.dumps(text)[1:-1] in rendered


class TestProjectForm:
    def test_number_inputs_send_raw_value_not_dom_target(self) -> None:
        rendered = str(project_form_fields())

        for handler in ("set_budget", "set_role_capacity"):
            assert "target" not in _handler_payload(rendered, handler)

    def test_budget_decimal_scale_is_a_prop_not_css(self) -> None:
        rendered = str(project_form_fields())

        assert '["decimalScale"]' not in rendered


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
