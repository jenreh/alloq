"""Shared helpers for tests that drive ``ChapterState`` handlers."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.states.chapter_state import ChapterState

from appkit_user.authentication.states import LoginState

MODULE = "alloq_offer.workshop.states.chapter_state"


def shows(text: str, event: str) -> bool:
    """Whether a toast event carries ``text`` (also as ``str()`` escapes it)."""
    return text in event or json.dumps(text)[1:-1] in event


@contextmanager
def as_editor(state: ChapterState, db: Any) -> Iterator[None]:
    """Run handlers as an offer editor of offer 1 against the test database."""
    user = MagicMock(is_admin=False, user_id=1, roles=["offer_editor"])
    user.name = "Anna"

    async def _user() -> MagicMock:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value=None)

    async def _get_state(cls: type) -> Any:
        return login if cls is LoginState else SimpleNamespace(offer_id=1)

    registry = MagicMock()
    registry.get.return_value = WorkshopConfig()
    object.__setattr__(state, "get_state", _get_state)
    with (
        patch(f"{MODULE}.get_asyncdb_session", db.session),
        patch(f"{MODULE}.service_registry", return_value=registry),
    ):
        try:
            yield
        finally:
            object.__delattr__(state, "get_state")


async def run(handler: Any, *args: Any) -> str:
    """Call a handler; the yielded or returned events as one string."""
    result = handler(*args)
    if hasattr(result, "__aiter__"):
        return " ".join([str(i) async for i in result if i is not None])
    result = await result
    return "" if result is None else str(result)
