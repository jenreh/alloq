# ruff: noqa: ARG001
"""A10: nobody without the offer editor role gets workshop data or actions."""

import importlib
import inspect
import pkgutil
from collections.abc import Callable
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import alloq_offer.workshop.states as states_package
import pytest
import reflex as rx
from alloq_commons.access import _NOT_AUTHORIZED_MSG, ACCESS_LEVEL_ATTR

from appkit_user.authentication.states import LoginState


def _workshop_states() -> list[type[rx.State]]:
    found: dict[str, type[rx.State]] = {}
    for info in pkgutil.iter_modules(states_package.__path__):
        module: ModuleType = importlib.import_module(
            f"{states_package.__name__}.{info.name}"
        )
        for _name, cls in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(cls, rx.State)
                and cls.__module__ == module.__name__
                and cls is not rx.State
            ):
                found[cls.__qualname__] = cls
    return list(found.values())


def _args(fn: Callable[..., Any]) -> list[Any]:
    values: list[Any] = []
    for parameter in list(inspect.signature(fn).parameters.values())[1:]:
        annotation = parameter.annotation
        if annotation is bool:
            values.append(True)
        elif annotation is int:
            values.append(1)
        elif annotation is str:
            values.append("x")
        elif annotation is dict or str(annotation).startswith("dict"):
            values.append({})
        else:
            values.append([])
    return values


def _guarded_handlers() -> list[tuple[type[rx.State], str, Callable[..., Any]]]:
    return [
        (state, name, handler.fn)
        for state in _workshop_states()
        for name, handler in state.event_handlers.items()
        if getattr(handler.fn, ACCESS_LEVEL_ATTR, None) == "offer_editor"
    ]


def _state_for(cls: type[rx.State], roles: list[str], *, anonymous: bool) -> Any:
    state = cls(_reflex_internal_init=True)  # ty: ignore[unknown-argument]
    user = None if anonymous else MagicMock(is_admin=False, user_id=7, roles=roles)

    async def _user() -> Any:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value="redirect")

    async def _get_state(requested: type) -> Any:
        if requested is LoginState:
            return login
        raise AssertionError("A denied call must not read further state")

    object.__setattr__(state, "get_state", _get_state)
    return state


async def _call(state: Any, fn: Callable[..., Any]) -> list[Any]:
    result = fn(state, *_args(fn))
    if hasattr(result, "__aiter__"):
        return [item async for item in result]
    return [await result]


def test_the_workshop_has_guarded_handlers() -> None:
    names = {f"{s.__name__}.{n}" for s, n, _ in _guarded_handlers()}
    assert {
        "ExportState.download_export",
        "WorkshopState.load_workshop",
        "ChapterState.load_chapters",
        "SourcesState.revoke_source",
        "ReviewState.accept_finding",
    } <= names
    assert len(names) > 40


@pytest.mark.parametrize(
    ("state", "name", "fn"),
    _guarded_handlers(),
    ids=lambda value: getattr(value, "__name__", None),
)
async def test_other_roles_are_denied_before_any_data_is_touched(
    state: type[rx.State], name: str, fn: Callable[..., Any]
) -> None:
    for roles in (["employee"], ["project_manager"], ["admin"]):
        instance = _state_for(state, roles, anonymous=False)
        outcome = await _call(instance, fn)
        assert len(outcome) == 1
        assert _NOT_AUTHORIZED_MSG in str(outcome[0])


@pytest.mark.parametrize(
    ("state", "name", "fn"),
    _guarded_handlers(),
    ids=lambda value: getattr(value, "__name__", None),
)
async def test_anonymous_callers_are_sent_to_login(
    state: type[rx.State], name: str, fn: Callable[..., Any]
) -> None:
    instance = _state_for(state, [], anonymous=True)
    assert await _call(instance, fn) == ["redirect"]
