"""Render-level tests for dashboard components."""

from __future__ import annotations

from alloq_dashboard.components.capacity_card import role_capacity_cards
from alloq_dashboard.components.dashboard_grid import dashboard_grid, scope_control
from alloq_dashboard.components.portfolio_drawer import portfolio_drawer
from alloq_dashboard.components.portfolio_path import portfolio_chains_card
from alloq_dashboard.pages import _greeting
from alloq_dashboard.states import PortfolioState, RoleCapacityState


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


def test_dashboard_grid_does_not_render_role_capacity() -> None:
    assert RoleCapacityState.get_name() not in str(dashboard_grid())


def test_dashboard_grid_renders_the_four_portfolio_cards() -> None:
    rendered = str(dashboard_grid())
    state_name = PortfolioState.get_name()
    for title in ("Zeit und Fortschritt", "Offene Risiken", "Ressourcenpfad"):
        assert title in rendered
    assert f"{state_name}.data" in rendered
    assert f"{state_name}.is_loading" in rendered
    assert f"{state_name}.error_message" in rendered


def test_scope_control_switches_scope() -> None:
    rendered = str(scope_control())
    assert "set_scope" in rendered
    assert "department" in rendered
    assert "team" in rendered


def test_portfolio_drawer_shows_project_and_risks() -> None:
    rendered = str(portfolio_drawer())
    state_name = PortfolioState.get_name()
    assert f"{state_name}.drawer" in rendered
    assert "selected_project" in rendered
    assert "cell_risks" in rendered
    assert "close_drawer" in rendered


def test_portfolio_drawer_shows_role_and_person() -> None:
    rendered = str(portfolio_drawer())
    assert "selected_role" in rendered
    assert "selected_person" in rendered
    assert "open_person" in rendered
    assert "open_role" in rendered


def test_chain_pills_open_project_role_and_person() -> None:
    rendered = str(portfolio_chains_card())
    for handler in ("open_project", "open_role", "open_person"):
        assert handler in rendered
    assert "person_id" in rendered
