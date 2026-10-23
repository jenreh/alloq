"""Open the workshop workspace of an offer, creating it on first use."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.entities import WorkspaceEntity
from alloq_offer.workshop.export.template_package import (
    DEFAULT_TEMPLATE_KEY,
    load_template,
)
from alloq_offer.workshop.repositories import workspace_repo

NO_WORKSPACE = "Zu diesem Angebot gibt es noch keine Werkstatt."


async def open_workspace(
    session: AsyncSession, offer_id: int, user: str
) -> WorkspaceEntity:
    """The workspace of ``offer_id``; a new one is bound to the current template."""
    existing = await workspace_repo.find_by_offer(session, offer_id)
    if existing is not None:
        return existing
    template = load_template(DEFAULT_TEMPLATE_KEY)
    workspace = WorkspaceEntity(
        offer_id=offer_id,
        template_key=template.key,
        template_version=template.version,
        created_by=user,
    )
    try:
        async with session.begin_nested():
            session.add(workspace)
    except IntegrityError:
        # A second tab created the workspace first.
        found = await workspace_repo.find_by_offer(session, offer_id)
        if found is None:
            raise
        return found
    return workspace
