"""Minimal-input project creation for the assign-project-to-employee flows.

Only name and code are asked for; every other column falls back to its entity
default or to a placeholder date range that stays editable on the full project
page. The full project form remains the path for complete project setup.
"""

import datetime
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from alloq_commons.entities import ProjectEntity
from alloq_commons.models.project import Project
from alloq_commons.repositories import project_repo

log = logging.getLogger(__name__)

NEW_PROJECT_VALUE = "__new__"
NEW_PROJECT_OPTION: dict[str, str] = {
    "value": NEW_PROJECT_VALUE,
    "label": "+ Neues Projekt anlegen",
}

MAX_CODE_LENGTH = 5
PLACEHOLDER_DURATION_DAYS = 90


class QuickProjectError(Exception):
    """Rejected quick-create input; the message is shown to the user."""


async def create_quick_project(
    session: AsyncSession,
    name: str,
    code: str,
) -> Project:
    """Create a project from name and code alone and return its read model.

    The caller owns the transaction and must commit.
    """
    clean_name = name.strip()
    clean_code = code.strip()
    if not clean_name:
        raise QuickProjectError("Bitte einen Projektnamen eingeben.")
    if not clean_code:
        raise QuickProjectError("Bitte ein Projektkürzel eingeben.")
    if len(clean_code) > MAX_CODE_LENGTH:
        raise QuickProjectError(
            f"Projektkürzel darf höchstens {MAX_CODE_LENGTH} Zeichen haben."
        )
    if await project_repo.find_by_code(session, clean_code):
        raise QuickProjectError(f"Projektkürzel '{clean_code}' ist bereits vergeben.")

    start_date = datetime.date.today()  # noqa: DTZ011
    entity = ProjectEntity(
        code=clean_code,
        name_de=clean_name,
        start_date=start_date,
        end_date=start_date + datetime.timedelta(days=PLACEHOLDER_DURATION_DAYS),
        budget=0,
    )
    await project_repo.create(session, entity)
    # A new project has no related rows yet, so the read model's collection
    # defaults already describe it correctly.
    project = Project(
        id=entity.id,
        code=entity.code,
        name_de=entity.name_de,
        start_date=entity.start_date,
        end_date=entity.end_date,
        state=entity.state,
        budget=entity.budget,
        color=entity.color,
    )
    log.debug("Quick-created project %s (id=%d)", project.code, project.id)
    return project
