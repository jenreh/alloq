"""AI system prompts in the "Angebote" administration (tab "Prompts")."""

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

import reflex as rx

from alloq_offer.workshop.services import prompts as prompt_store
from alloq_offer.workshop.services.prompts import PromptError
from alloq_offer.workshop.states.helpers import browser_int, current_user_name
from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.decorators import requires_admin

logger = logging.getLogger(__name__)

LOAD_ERROR = "Die Prompts konnten nicht geladen werden."
SAVE_ERROR = "Der Prompt konnte nicht gespeichert werden."
SAVED = "Der Prompt wurde als neue Version gespeichert und ist aktiv."
ACTIVATED = "Diese Version des Prompts ist jetzt aktiv."


class PromptAdminState(rx.State):
    """Admins save new versions of the system prompts or go back to older ones."""

    prompts: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    name: rx.Field[str] = rx.field(prompt_store.CHAPTER_PROMPT)
    text: rx.Field[str] = rx.field("")
    versions: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)

    @rx.var
    def selected(self) -> dict[str, Any]:
        return next((p for p in self.prompts if p["name"] == self.name), {})

    @rx.var
    def changed(self) -> bool:
        return self.text.strip() != str(self.selected.get("text", "")).strip()

    async def _reload(self) -> None:
        self.prompts = await prompt_store.list_prompts(get_asyncdb_session)
        self.text = str(self.selected.get("text", ""))
        self.versions = await prompt_store.prompt_versions(
            get_asyncdb_session, self.name
        )

    async def _load(self) -> Any | None:
        """Reload; a toast when that failed."""
        try:
            await self._reload()
        except Exception:
            logger.exception("Loading prompt %s failed", self.name)
            return rx.toast.error(LOAD_ERROR, position="top-right")
        return None

    async def _change(self, action: Callable[[], Awaitable[Any]], done: str) -> Any:
        """Run ``action`` and reload; the toast tells how it went."""
        try:
            await action()
        except PromptError as exc:
            return rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Changing prompt %s failed", self.name)
            return rx.toast.error(SAVE_ERROR, position="top-right")
        return await self._load() or rx.toast.success(done, position="top-right")

    @rx.event
    @requires_admin
    async def load_prompts(self) -> AsyncGenerator[Any]:
        yield await self._load()

    @rx.event
    @requires_admin
    async def select_prompt(self, name: str) -> AsyncGenerator[Any]:
        if name not in prompt_store.PROMPT_NAMES:
            return
        previous, self.name = self.name, name
        failed = await self._load()
        if failed:
            self.name = previous
        yield failed

    @rx.event
    def set_text(self, value: str) -> None:
        self.text = value

    @rx.event
    @requires_admin
    async def save(self) -> AsyncGenerator[Any]:
        user, name, text = await current_user_name(self), self.name, self.text
        yield await self._change(
            lambda: prompt_store.save_prompt(get_asyncdb_session, name, text, user),
            SAVED,
        )

    @rx.event
    @requires_admin
    async def activate(self, version: int) -> AsyncGenerator[Any]:
        name, number = self.name, browser_int(version)
        if number is None:
            return
        yield await self._change(
            lambda: prompt_store.activate_prompt(get_asyncdb_session, name, number),
            ACTIVATED,
        )
