"""Project load for the planning page, without the allocation history."""

import logging
from collections.abc import Iterable

from alloq_commons.models.project import Project
from alloq_commons.repositories import capacity_allocation_repo, project_repo
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def team_initials_by_project(
    staffed: Iterable[tuple[int, str, str]],
) -> dict[int, list[str]]:
    """Initials per project from (project id, first name, last name) rows."""
    initials: dict[int, list[str]] = {}
    for project_id, first_name, last_name in staffed:
        initials.setdefault(project_id, []).append(f"{first_name[:1]}{last_name[:1]}")
    return initials


async def load_planning_projects(session: AsyncSession) -> list[Project]:
    """All projects as read models, team initials from one grouped query."""
    entities = await project_repo.find_all_for_planning(session)
    staffed = await capacity_allocation_repo.find_staffed_employees(session)
    initials = team_initials_by_project(tuple(row) for row in staffed)
    logger.debug("Loaded %d projects for planning", len(entities))
    return [
        Project(**{**e.to_dict(), "team_initials": initials.get(e.id, [])})
        for e in entities
    ]
