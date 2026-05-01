import logging
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_commons.entities import RoleEntity
from alloq_commons.models import Role, RoleCreate
from alloq_commons.repositories import role_repo

from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.decorators import is_authenticated

logger = logging.getLogger(__name__)


class RoleState(rx.State):
    """State for organizational role management."""

    roles: list[Role] = []
    selected_role: Role | None = None
    is_loading: bool = False

    add_modal_open: bool = False
    edit_modal_open: bool = False
    search_filter: str = ""

    def set_search_filter(self, value: str) -> None:
        """Update the search filter."""
        self.search_filter = value

    @rx.var
    def filtered_roles(self) -> list[Role]:
        """Return roles filtered by search text (name or description)."""
        if not self.search_filter:
            return self.roles
        search = self.search_filter.lower()
        return [
            r
            for r in self.roles
            if search in r.name.lower() or search in r.description.lower()
        ]

    def open_add_modal(self) -> None:
        """Open the add role modal."""
        self.add_modal_open = True

    def close_add_modal(self) -> None:
        """Close the add role modal."""
        self.add_modal_open = False

    def open_edit_modal(self) -> None:
        """Open the edit role modal."""
        self.edit_modal_open = True

    def close_edit_modal(self) -> None:
        """Close the edit role modal and reset selection."""
        self.edit_modal_open = False
        self.selected_role = None

    async def select_role_and_open_edit(self, role_id: int) -> None:
        """Select a role by ID and open the edit modal."""
        await self._select_role(role_id)
        self.open_edit_modal()

    async def _select_role(self, role_id: int) -> None:
        """Load a role by ID into selected_role."""
        async with get_asyncdb_session() as session:
            entity = await role_repo.find_by_id(session, role_id)
            if entity:
                self.selected_role = Role(**entity.to_dict())

    async def _load_roles(self, limit: int = 200, offset: int = 0) -> None:
        """Internal load logic."""
        async with get_asyncdb_session() as session:
            entities = await role_repo.find_all_paginated(
                session, limit=limit, offset=offset
            )
            self.roles = [Role(**e.to_dict()) for e in entities]

    @is_authenticated
    async def load_roles(
        self, limit: int = 200, offset: int = 0
    ) -> AsyncGenerator[Any, None]:
        """Load all roles from the database."""
        self.is_loading = True
        yield
        try:
            await self._load_roles(limit, offset)
        finally:
            self.is_loading = False

    @is_authenticated
    async def create_role(self, form_data: dict) -> AsyncGenerator[Any, None]:
        """Create a new role from form submission."""
        self.is_loading = True
        yield
        try:
            role_data = RoleCreate(
                name=form_data.get("name", "").strip(),
                description=form_data.get("description", "").strip(),
            )

            async with get_asyncdb_session() as session:
                entity = RoleEntity(
                    name=role_data.name,
                    description=role_data.description or None,
                )
                await role_repo.create(session, entity)

            await self._load_roles()
            self.close_add_modal()
            self.is_loading = False
            yield rx.toast.info(
                f"Rolle '{role_data.name}' wurde erstellt.",
                position="top-right",
            )
        except Exception as e:
            logger.error("Failed to create role: %s", e)
            self.is_loading = False
            yield rx.toast.error(
                f"Fehler beim Erstellen: {e}",
                position="top-right",
            )

    @is_authenticated
    async def update_role(self, form_data: dict) -> AsyncGenerator[Any, None]:
        """Update an existing role from form submission."""
        self.is_loading = True
        yield
        try:
            if not self.selected_role:
                self.is_loading = False
                yield rx.toast.error("Keine Rolle ausgewählt.", position="top-right")
                return

            role_data = RoleCreate(
                name=form_data.get("name", "").strip(),
                description=form_data.get("description", "").strip(),
            )

            async with get_asyncdb_session() as session:
                entity = await role_repo.find_by_id(session, self.selected_role.id)
                if not entity:
                    self.is_loading = False
                    yield rx.toast.error("Rolle nicht gefunden.", position="top-right")
                    return
                entity.name = role_data.name
                entity.description = role_data.description or None
                await role_repo.update(session, entity)

            await self._load_roles()
            self.close_edit_modal()
            self.is_loading = False
            yield rx.toast.info(
                f"Rolle '{role_data.name}' wurde aktualisiert.",
                position="top-right",
            )
        except Exception as e:
            logger.error("Failed to update role: %s", e)
            self.is_loading = False
            yield rx.toast.error(
                f"Fehler beim Aktualisieren: {e}",
                position="top-right",
            )

    @is_authenticated
    async def delete_role(self, role_id: int) -> AsyncGenerator[Any, None]:
        """Delete a role by ID (hard-delete)."""
        self.is_loading = True
        yield
        try:
            async with get_asyncdb_session() as session:
                entity = await role_repo.find_by_id(session, role_id)
                if not entity:
                    self.is_loading = False
                    yield rx.toast.error("Rolle nicht gefunden.", position="top-right")
                    return

                deleted = await role_repo.delete_by_id(session, role_id)
                if not deleted:
                    self.is_loading = False
                    yield rx.toast.error(
                        "Rolle konnte nicht gelöscht werden.",
                        position="top-right",
                    )
                    return

            await self._load_roles()
            self.is_loading = False
            yield rx.toast.info("Rolle wurde gelöscht.", position="top-right")
        except Exception as e:
            logger.error("Failed to delete role: %s", e)
            self.is_loading = False
            yield rx.toast.error(
                f"Fehler beim Löschen: {e}",
                position="top-right",
            )
