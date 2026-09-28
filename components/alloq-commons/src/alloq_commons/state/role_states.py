import logging
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_commons.entities import RoleEntity
from alloq_commons.models import Role, RoleCreate
from alloq_commons.repositories import role_repo
from sqlalchemy.exc import IntegrityError

from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.decorators import requires_admin

logger = logging.getLogger(__name__)


class RoleState(rx.State):
    """State for organizational role management."""

    roles: rx.Field[list[Role]] = rx.field(default_factory=list)
    selected_role: rx.Field[Role | None] = rx.field(None)
    is_loading: rx.Field[bool] = rx.field(False)

    add_modal_open: rx.Field[bool] = rx.field(False)
    edit_modal_open: rx.Field[bool] = rx.field(False)
    search_filter: rx.Field[str] = rx.field("")

    @rx.event
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

    @rx.event
    def open_add_modal(self) -> None:
        """Open the add role modal."""
        self.add_modal_open = True

    @rx.event
    def close_add_modal(self) -> None:
        """Close the add role modal."""
        self.add_modal_open = False

    @rx.event
    def open_edit_modal(self) -> None:
        """Open the edit role modal."""
        self.edit_modal_open = True

    @rx.event
    def close_edit_modal(self) -> None:
        """Close the edit role modal and reset selection."""
        self.edit_modal_open = False
        self.selected_role = None

    @rx.event
    @requires_admin
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

    @rx.event
    @requires_admin
    async def load_roles(
        self, limit: int = 200, offset: int = 0
    ) -> AsyncGenerator[Any]:
        """Load all roles from the database.

        The loading row only replaces the table on the first load; revisits
        refresh the existing rows in place to avoid a flicker.
        """
        if not self.roles:
            self.is_loading = True
            yield
        try:
            await self._load_roles(limit, offset)
        finally:
            self.is_loading = False

    @rx.event
    @requires_admin
    async def create_role(self, form_data: dict) -> AsyncGenerator[Any]:
        """Create a new role from form submission."""
        self.is_loading = True
        yield
        try:
            role_data = RoleCreate(
                name=form_data.get("name", "").strip(),
                abbreviation=form_data.get("abbreviation", "").strip(),
                description=form_data.get("description", "").strip(),
                ramp_up=form_data.get("ramp_up") == "on",
                ramp_down=form_data.get("ramp_down") == "on",
            )

            async with get_asyncdb_session() as session:
                entity = RoleEntity(
                    name=role_data.name,
                    abbreviation=role_data.abbreviation,
                    description=role_data.description or None,
                    ramp_up=role_data.ramp_up,
                    ramp_down=role_data.ramp_down,
                )
                await role_repo.create(session, entity)

            await self._load_roles()
            self.close_add_modal()
            self.is_loading = False
            yield rx.toast.info(
                f"Rolle '{role_data.name}' wurde erstellt.",
                position="top-right",
            )
        except Exception:
            logger.exception("Failed to create role")
            self.is_loading = False
            yield rx.toast.error(
                "Fehler beim Erstellen der Rolle.",
                position="top-right",
            )

    @rx.event
    @requires_admin
    async def update_role(self, form_data: dict) -> AsyncGenerator[Any]:
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
                abbreviation=form_data.get("abbreviation", "").strip(),
                description=form_data.get("description", "").strip(),
                ramp_up=form_data.get("ramp_up") == "on",
                ramp_down=form_data.get("ramp_down") == "on",
            )

            # Toasts are yielded only after the session is closed so the DB
            # connection is not held across a websocket round trip.
            async with get_asyncdb_session() as session:
                entity = await role_repo.find_by_id(session, self.selected_role.id)
                if entity:
                    entity.name = role_data.name
                    entity.abbreviation = role_data.abbreviation
                    entity.description = role_data.description or None
                    entity.ramp_up = role_data.ramp_up
                    entity.ramp_down = role_data.ramp_down
                    await role_repo.update(session, entity)
            if not entity:
                self.is_loading = False
                yield rx.toast.error("Rolle nicht gefunden.", position="top-right")
                return

            await self._load_roles()
            self.close_edit_modal()
            self.is_loading = False
            yield rx.toast.info(
                f"Rolle '{role_data.name}' wurde aktualisiert.",
                position="top-right",
            )
        except Exception:
            logger.exception("Failed to update role")
            self.is_loading = False
            yield rx.toast.error(
                "Fehler beim Aktualisieren der Rolle.",
                position="top-right",
            )

    @rx.event
    @requires_admin
    async def delete_role(self, role_id: int) -> AsyncGenerator[Any]:
        """Delete a role by ID (hard-delete)."""
        self.is_loading = True
        yield
        try:
            error = ""
            async with get_asyncdb_session() as session:
                entity = await role_repo.find_by_id(session, role_id)
                if not entity:
                    error = "Rolle nicht gefunden."
                elif not await role_repo.delete_by_id(session, role_id):
                    error = "Rolle konnte nicht gelöscht werden."
            if error:
                self.is_loading = False
                yield rx.toast.error(error, position="top-right")
                return

            await self._load_roles()
            self.is_loading = False
            yield rx.toast.info("Rolle wurde gelöscht.", position="top-right")
        except IntegrityError:
            logger.warning("Role %d is still referenced; delete rejected", role_id)
            self.is_loading = False
            yield rx.toast.error(
                "Rolle wird noch verwendet und kann nicht gelöscht werden.",
                position="top-right",
            )
        except Exception:
            logger.exception("Failed to delete role")
            self.is_loading = False
            yield rx.toast.error(
                "Fehler beim Löschen der Rolle.",
                position="top-right",
            )
