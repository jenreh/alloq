import logging
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_commons.entities import DepartmentEntity
from alloq_commons.models import Department, DepartmentCreate
from alloq_commons.repositories import department_repo
from alloq_commons.roles import ALL_ROLES, department_roles
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.decorators import requires_admin
from appkit_user.user_management.states.user_states import UserState

logger = logging.getLogger(__name__)

DUPLICATE_MESSAGE = "Name oder Kürzel ist bereits vergeben."


def _department_from_form(form_data: dict) -> DepartmentCreate:
    return DepartmentCreate(
        name=form_data.get("name", "").strip(),
        abbreviation=form_data.get("abbreviation", "").strip(),
        highlighted=form_data.get("highlighted") == "on",
    )


async def load_departments() -> list[Department]:
    """All departments ordered by name."""
    async with get_asyncdb_session() as session:
        entities = await department_repo.find_all_paginated(session)
        return [Department(**e.to_dict()) for e in entities]


class DepartmentState(rx.State):
    """State for department management."""

    departments: rx.Field[list[Department]] = rx.field(default_factory=list)
    selected_department: rx.Field[Department | None] = rx.field(None)
    is_loading: rx.Field[bool] = rx.field(False)

    add_modal_open: rx.Field[bool] = rx.field(False)
    edit_modal_open: rx.Field[bool] = rx.field(False)
    search_filter: rx.Field[str] = rx.field("")

    @rx.event
    def set_search_filter(self, value: str) -> None:
        self.search_filter = value

    @rx.var
    def filtered_departments(self) -> list[Department]:
        """Departments filtered by search text (name or abbreviation)."""
        if not self.search_filter:
            return self.departments
        search = self.search_filter.lower()
        return [
            d
            for d in self.departments
            if search in d.name.lower() or search in d.abbreviation.lower()
        ]

    @rx.event
    def open_add_modal(self) -> None:
        self.add_modal_open = True

    @rx.event
    def close_add_modal(self) -> None:
        self.add_modal_open = False

    @rx.event
    def close_edit_modal(self) -> None:
        self.edit_modal_open = False
        self.selected_department = None

    @rx.event
    @requires_admin
    async def select_department_and_open_edit(self, department_id: int) -> None:
        async with get_asyncdb_session() as session:
            entity = await department_repo.find_by_id(session, department_id)
            if entity:
                self.selected_department = Department(**entity.to_dict())
        self.edit_modal_open = self.selected_department is not None

    @rx.event
    @requires_admin
    async def load_departments(self) -> AsyncGenerator[Any]:
        """Load all departments; the loading row only shows on the first load."""
        if not self.departments:
            self.is_loading = True
            yield
        try:
            self.departments = await load_departments()
        finally:
            self.is_loading = False

    @rx.event
    @requires_admin
    async def load_user_roles(self) -> None:
        """Offer the app roles plus one role per department in user management."""
        roles = [*ALL_ROLES, *department_roles(await load_departments())]
        users = await self.get_state(UserState)
        users.set_available_roles(roles)

    @rx.event
    @requires_admin
    async def create_department(self, form_data: dict) -> AsyncGenerator[Any]:
        """Create a department from form submission."""
        try:
            data = _department_from_form(form_data)
            async with get_asyncdb_session() as session:
                await department_repo.create(
                    session,
                    DepartmentEntity(
                        name=data.name,
                        abbreviation=data.abbreviation,
                        highlighted=data.highlighted,
                    ),
                )
        except ValidationError:
            yield rx.toast.error("Name und Kürzel angeben.", position="top-right")
            return
        except IntegrityError:
            yield rx.toast.error(DUPLICATE_MESSAGE, position="top-right")
            return
        except Exception:
            logger.exception("Failed to create department")
            yield rx.toast.error(
                "Fehler beim Erstellen der Abteilung.", position="top-right"
            )
            return

        self.departments = await load_departments()
        self.add_modal_open = False
        yield rx.toast.info(
            f"Abteilung '{data.name}' wurde erstellt.", position="top-right"
        )

    @rx.event
    @requires_admin
    async def update_department(self, form_data: dict) -> AsyncGenerator[Any]:
        """Update the selected department from form submission."""
        if not self.selected_department:
            yield rx.toast.error("Keine Abteilung ausgewählt.", position="top-right")
            return
        try:
            data = _department_from_form(form_data)
            async with get_asyncdb_session() as session:
                entity = await department_repo.find_by_id(
                    session, self.selected_department.id
                )
                if entity:
                    entity.name = data.name
                    entity.abbreviation = data.abbreviation
                    entity.highlighted = data.highlighted
                    await department_repo.update(session, entity)
        except ValidationError:
            yield rx.toast.error("Name und Kürzel angeben.", position="top-right")
            return
        except IntegrityError:
            yield rx.toast.error(DUPLICATE_MESSAGE, position="top-right")
            return
        except Exception:
            logger.exception("Failed to update department")
            yield rx.toast.error(
                "Fehler beim Aktualisieren der Abteilung.", position="top-right"
            )
            return
        if not entity:
            yield rx.toast.error("Abteilung nicht gefunden.", position="top-right")
            return

        self.departments = await load_departments()
        self.close_edit_modal()
        yield rx.toast.info(
            f"Abteilung '{data.name}' wurde aktualisiert.", position="top-right"
        )

    @rx.event
    @requires_admin
    async def delete_department(self, department_id: int) -> AsyncGenerator[Any]:
        """Delete a department; its employees keep no department."""
        try:
            async with get_asyncdb_session() as session:
                deleted = await department_repo.delete_by_id(session, department_id)
        except Exception:
            logger.exception("Failed to delete department %d", department_id)
            yield rx.toast.error(
                "Fehler beim Löschen der Abteilung.", position="top-right"
            )
            return
        if not deleted:
            yield rx.toast.error("Abteilung nicht gefunden.", position="top-right")
            return

        self.departments = await load_departments()
        yield rx.toast.info("Abteilung wurde gelöscht.", position="top-right")
