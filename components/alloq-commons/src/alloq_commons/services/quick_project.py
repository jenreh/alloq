"""Minimal-input project creation for the assign-project-to-employee flows.

Only name and code are asked for; every other column falls back to its entity
default or to a placeholder date range that stays editable on the full project
page. The full project form remains the path for complete project setup.
"""

import datetime as dt
import logging
from collections.abc import Iterable
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_commons.entities import ProjectEntity
from alloq_commons.entities.project import ProjectStateEnum
from alloq_commons.models.project import Project
from alloq_commons.repositories import project_repo

log = logging.getLogger(__name__)

NEW_PROJECT_VALUE = "__new__"
NEW_PROJECT_OPTION: dict[str, str] = {
    "value": NEW_PROJECT_VALUE,
    "label": "+ Neues Projekt anlegen",
}

STATE_GROUPS: tuple[tuple[str, frozenset[str]], ...] = (
    ("Aktiv", frozenset({ProjectStateEnum.ACTIVE, ProjectStateEnum.AT_RISK})),
    ("Geplant", frozenset({ProjectStateEnum.PLANNED})),
    ("Abgeschlossen", frozenset({ProjectStateEnum.COMPLETED})),
)

MAX_CODE_LENGTH = 5
PLACEHOLDER_DURATION_DAYS = 90


def grouped_project_options(projects: Iterable[Project]) -> list[dict[str, Any]]:
    """Build select data: the create entry, then projects grouped by state.

    Groups follow ``STATE_GROUPS`` (completed last); empty groups are omitted.
    """
    buckets: dict[str, list[dict[str, str]]] = {name: [] for name, _ in STATE_GROUPS}
    for p in projects:
        name = next((n for n, states in STATE_GROUPS if p.state in states), "Geplant")
        buckets[name].append({"value": str(p.id), "label": f"{p.code} - {p.name_de}"})
    return [
        NEW_PROJECT_OPTION,
        *({"group": name, "items": items} for name, items in buckets.items() if items),
    ]


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

    start_date = dt.date.today()  # noqa: DTZ011
    entity = ProjectEntity(
        code=clean_code,
        name_de=clean_name,
        start_date=start_date,
        end_date=start_date + dt.timedelta(days=PLACEHOLDER_DURATION_DAYS),
        budget=0,
    )
    try:
        await project_repo.create(session, entity)
    except IntegrityError as exc:
        # A concurrent create took the code between the check and the insert.
        raise QuickProjectError(
            f"Projektkürzel '{clean_code}' ist bereits vergeben."
        ) from exc
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
