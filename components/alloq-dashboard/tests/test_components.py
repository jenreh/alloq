"""Render-level tests for dashboard components."""

from __future__ import annotations

from alloq_dashboard.components.capacity_card import role_capacity_cards
from alloq_dashboard.pages import _greeting
from alloq_dashboard.states import RoleCapacityState


def test_greeting_uses_authenticated_user_name() -> None:
    rendered = str(_greeting())
    assert "Jens" not in rendered
    assert '["name"]' in rendered
    assert "Willkommen zur" in rendered


def test_role_capacity_cards_render_loading_and_error_states() -> None:
    rendered = str(role_capacity_cards())
    state_name = RoleCapacityState.get_name()
    assert f"{state_name}.error_message" in rendered
    assert f"{state_name}.is_loading" in rendered
