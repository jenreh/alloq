"""Tests for the daily rates (Tagessätze) administration."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_commons.components.daily_rate import (
    COLUMN_LABELS,
    EMPTY_TEXT,
    daily_rates_table,
    daily_rates_toolbar,
    margin_settings,
)
from alloq_commons.entities import DailyRateEntity, RoleEntity
from alloq_commons.models import (
    DailyRate,
    DailyRateSettingsUpdate,
    DailyRateUpdate,
    Role,
)
from alloq_commons.repositories import daily_rate_repo
from alloq_commons.state.daily_rate_states import (
    INVALID_MARGIN_MESSAGE,
    DailyRateState,
    _parse_euros,
)
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from appkit_user.authentication.states import LoginState

MODULE = "alloq_commons.state.daily_rate_states"


def _role(role_id: int, name: str) -> RoleEntity:
    entity = RoleEntity(name=name, abbreviation="", ramp_up=False, ramp_down=False)
    entity.id = role_id
    return entity


def _rate(
    rate_id: int = 5, role_id: int = 1, cost: int | None = 780, **prices: Any
) -> DailyRateEntity:
    entity = DailyRateEntity(role_id=role_id, production_cost=cost, **prices)
    entity.id = rate_id
    entity.role = _role(role_id, "Data Scientist")
    return entity


@pytest.fixture
def repo() -> Iterator[AsyncMock]:
    """Patch the repositories and the DB session."""
    session = AsyncMock()

    @asynccontextmanager
    async def _ctx() -> AsyncIterator[Any]:
        yield session

    mock = AsyncMock()
    mock.find_all_by_role_name = AsyncMock(return_value=[_rate()])
    mock.find_by_role_id = AsyncMock(return_value=None)
    mock.get_margins = AsyncMock(return_value=(30, 35))
    roles = AsyncMock()
    roles.find_all_paginated = AsyncMock(
        return_value=[_role(1, "Data Scientist"), _role(2, "Entwickler")]
    )
    with (
        patch(f"{MODULE}.daily_rate_repo", mock),
        patch(f"{MODULE}.role_repo", roles),
        patch(f"{MODULE}.get_asyncdb_session", _ctx),
    ):
        yield mock


@contextmanager
def _as_admin(state: DailyRateState) -> Iterator[None]:
    user = MagicMock(is_admin=True, user_id=1)

    async def _user() -> MagicMock:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value=None)

    async def _get_state(cls: type) -> Any:
        assert cls is LoginState
        return login

    object.__setattr__(state, "get_state", _get_state)
    try:
        yield
    finally:
        object.__delattr__(state, "get_state")


async def _run(handler: Any, *args: Any) -> str:
    """Drive a handler and return its toasts as text."""
    result = handler(*args)
    if hasattr(result, "__aiter__"):
        return " ".join([str(i) async for i in result if i is not None])
    await result
    return ""


def _state() -> DailyRateState:
    state = DailyRateState()
    state.roles = [Role(id=1, name="Data Scientist"), Role(id=2, name="Entwickler")]
    state.rates = [DailyRate(id=5, role_id=1, production_cost=780)]
    return state


class TestDailyRateModels:
    def test_to_dict_includes_role_and_prices(self) -> None:
        data = _rate(list_price=1300).to_dict()
        assert data["role_name"] == "Data Scientist"
        assert (data["production_cost"], data["list_price"]) == (780, 1300)

    @pytest.mark.parametrize(
        "data",
        [{"production_cost": 0}, {"list_price": 100_001}, {"list_price": -5}],
    )
    def test_prices_must_be_positive_and_bounded(self, data: dict) -> None:
        with pytest.raises(ValidationError):
            DailyRateUpdate(**data)

    def test_update_without_prices_is_empty(self) -> None:
        assert DailyRateUpdate().is_empty is True
        assert DailyRateUpdate(list_price=10).is_empty is False

    @pytest.mark.parametrize(("minimum", "margin"), [(-1, 35), (30, 91), (36, 35)])
    def test_margins_stay_in_range_and_ordered(self, minimum: int, margin: int) -> None:
        with pytest.raises(ValidationError):
            DailyRateSettingsUpdate(
                min_contribution_margin_percent=minimum,
                contribution_margin_percent=margin,
            )


class TestDailyRateRepository:
    async def test_margins_default_and_can_be_saved(
        self, async_session: AsyncSession
    ) -> None:
        assert await daily_rate_repo.get_margins(async_session) == (30, 35)
        await daily_rate_repo.save_margins(async_session, 25, 40)
        await daily_rate_repo.save_margins(async_session, 28, 38)
        assert await daily_rate_repo.get_margins(async_session) == (28, 38)

    async def test_rates_by_role(self, async_session: AsyncSession) -> None:
        tester = RoleEntity(name="Tester", abbreviation="")
        architect = RoleEntity(name="Architekt", abbreviation="")
        async_session.add_all([tester, architect])
        await async_session.flush()
        async_session.add_all(
            [
                DailyRateEntity(role_id=tester.id, production_cost=400),
                DailyRateEntity(role_id=architect.id, list_price=1300),
            ]
        )
        await async_session.flush()
        rates = await daily_rate_repo.find_all_by_role_name(async_session)
        assert [r.to_dict()["role_name"] for r in rates] == ["Architekt", "Tester"]
        found = await daily_rate_repo.find_by_role_id(async_session, tester.id)
        assert found is not None
        assert found.production_cost == 400


class TestParsing:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [("1.120 €", 1120), ("780", 780), ("", None), (None, None), (950.0, 950)],
    )
    def test_parse_euros(self, value: Any, expected: int | None) -> None:
        assert _parse_euros(value) == expected


class TestDailyRateState:
    @pytest.mark.usefixtures("repo")
    async def test_load(self) -> None:
        state = DailyRateState()
        with _as_admin(state):
            await _run(state.load_daily_rates)
        assert [r.role_name for r in state.rows] == ["Data Scientist", "Entwickler"]
        assert (state.min_margin, state.margin) == (30, 35)
        assert (state.min_margin_draft, state.margin_draft) == (30, 35)
        assert state.is_loading is False

    async def test_load_error_shows_toast(self, repo: AsyncMock) -> None:
        repo.find_all_by_role_name = AsyncMock(side_effect=RuntimeError("db"))
        state = DailyRateState()
        with _as_admin(state):
            text = await _run(state.load_daily_rates)
        assert "Fehler beim Laden" in text
        assert state.is_loading is False

    def test_rows_list_every_role_with_prices(self) -> None:
        state = _state()
        first, second = state.rows
        assert (first.recommended_price, first.effective_list_price) == (1120, 1200)
        assert (second.role_name, second.production_cost) == ("Entwickler", None)
        assert second.recommended_price is None
        state.search_filter = "entw"
        assert [r.role_id for r in state.rows] == [2]

    def test_rows_follow_margin_inputs_while_typing(self) -> None:
        state = _state()
        state.set_min_margin_draft(35.0)
        state.set_margin_draft("")
        assert state.rows[0].recommended_price == 1200
        assert state.rows[0].effective_list_price == 780
        state.set_search_filter("x")
        assert state.search_filter == "x"

    async def test_save_cost_creates_rate(self, repo: AsyncMock) -> None:
        state = _state()
        with _as_admin(state):
            text = await _run(state.save_production_cost, 2, "650 €")
        created = repo.create.await_args.args[1]
        assert (created.role_id, created.production_cost) == (2, 650)
        assert created.list_price is None
        assert text == ""
        repo.find_all_by_role_name.assert_awaited()

    async def test_unchanged_value_is_not_saved(self, repo: AsyncMock) -> None:
        state = _state()
        with _as_admin(state):
            await _run(state.save_production_cost, 1, "780 €")
            await _run(state.save_list_price, 2, "")
        repo.find_by_role_id.assert_not_awaited()

    async def test_manual_list_price_is_stored(self, repo: AsyncMock) -> None:
        entity = _rate()
        repo.find_by_role_id = AsyncMock(return_value=entity)
        state = _state()
        with _as_admin(state):
            await _run(state.save_list_price, 1, "1.300 €")
        assert entity.list_price == 1300
        repo.update.assert_awaited_once()

    async def test_price_equal_to_calculated_clears_manual_price(
        self, repo: AsyncMock
    ) -> None:
        entity = _rate(list_price=1300)
        repo.find_by_role_id = AsyncMock(return_value=entity)
        state = _state()
        state.rates = [DailyRate(id=5, role_id=1, production_cost=780, list_price=1300)]
        with _as_admin(state):
            await _run(state.save_list_price, 1, "1.200 €")
        assert entity.list_price is None

    async def test_clearing_last_price_deletes_rate(self, repo: AsyncMock) -> None:
        repo.find_by_role_id = AsyncMock(return_value=_rate())
        state = _state()
        with _as_admin(state):
            await _run(state.save_production_cost, 1, "")
        repo.delete_by_id.assert_awaited_once()
        assert repo.delete_by_id.await_args.args[1] == 5

    async def test_invalid_price_shows_message(self, repo: AsyncMock) -> None:
        state = _state()
        version = state.form_version
        with _as_admin(state):
            text = await _run(state.save_list_price, 2, "200.000 €")
        assert "zwischen 1 und" in text
        repo.create.assert_not_awaited()
        assert state.form_version == version + 1

    async def test_save_error_shows_toast(self, repo: AsyncMock) -> None:
        repo.create = AsyncMock(side_effect=RuntimeError("db"))
        state = _state()
        with _as_admin(state):
            text = await _run(state.save_production_cost, 2, "500")
        assert "Fehler beim Speichern" in text

    async def test_save_margins(self, repo: AsyncMock) -> None:
        state = DailyRateState()
        state.set_min_margin_draft(28)
        state.set_margin_draft(40)
        with _as_admin(state):
            text = await _run(state.save_margins)
        assert repo.save_margins.await_args.args[1:] == (28, 40)
        assert (state.min_margin, state.margin) == (28, 40)
        assert "gespeichert" in text

    async def test_unchanged_margins_are_not_saved(self, repo: AsyncMock) -> None:
        state = DailyRateState()
        with _as_admin(state):
            await _run(state.save_margins)
        repo.save_margins.assert_not_awaited()

    async def test_minimum_above_margin_is_rejected(self, repo: AsyncMock) -> None:
        state = DailyRateState()
        state.set_min_margin_draft(40)
        with _as_admin(state):
            text = await _run(state.save_margins)
        repo.save_margins.assert_not_awaited()
        assert INVALID_MARGIN_MESSAGE.split("ü")[0] in text
        assert (state.min_margin_draft, state.min_margin) == (30, 30)

    async def test_save_margins_error(self, repo: AsyncMock) -> None:
        repo.save_margins = AsyncMock(side_effect=RuntimeError("db"))
        state = DailyRateState()
        state.set_margin_draft(40)
        with _as_admin(state):
            text = await _run(state.save_margins)
        assert "Fehler beim Speichern" in text
        assert (state.margin, state.margin_draft) == (35, 35)


class TestDailyRateComponents:
    def test_table_has_price_inputs_per_role(self) -> None:
        rendered = str(daily_rates_table())
        assert "rows" in rendered
        assert "save_production_cost" in rendered
        assert "save_list_price" in rendered
        assert "recommended_price" in rendered
        assert "readOnly:true" in rendered
        assert 'thousandSeparator:"."' in rendered
        assert EMPTY_TEXT in rendered
        assert all(label in rendered for label in COLUMN_LABELS)

    def test_toolbar_has_search_only(self) -> None:
        assert len(daily_rates_toolbar()) == 1

    def test_margin_settings_save_on_blur(self) -> None:
        rendered = str(margin_settings())
        assert 'suffix:" %"' in rendered
        assert "save_margins" in rendered
        assert "set_min_margin_draft" in rendered
