"""Open the workshop workspace of an offer, creating it on first use."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.entities import WorkspaceEntity
from alloq_offer.workshop.export.template_package import DEFAULT_TEMPLATE_KEY
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.chapters import create_chapters
from alloq_offer.workshop.services.templates import latest_template, version_number

NO_WORKSPACE = "Zu diesem Angebot gibt es noch keine Werkstatt."


def template_label(workspace: WorkspaceEntity) -> str:
    """``QUO V1 · Version 2``: the template and version the offer is bound to."""
    name = workspace.template_key.replace("_", " ").upper()
    return f"{name} · Version {version_number(workspace.template_version)}"


async def open_workspace(
    session: AsyncSession, offer_id: int, user: str
) -> WorkspaceEntity:
    """The workspace of ``offer_id``; a new one binds the latest template version.

    The new offer copies the outline of that version into its own chapters, so a
    later template change never alters it (spec 6.1).
    """
    existing = await workspace_repo.find_by_offer(session, offer_id)
    if existing is not None:
        return existing
    template = await latest_template(session, DEFAULT_TEMPLATE_KEY)
    workspace = WorkspaceEntity(
        offer_id=offer_id,
        template_key=template.key,
        template_version=template.version,
        created_by=user,
    )
    try:
        async with session.begin_nested():
            session.add(workspace)
            await session.flush()
            await create_chapters(session, offer_id, template, map_revision=0)
    except IntegrityError:
        # A second tab created the workspace first.
        found = await workspace_repo.find_by_offer(session, offer_id)
        if found is None:
            raise
        return found
    return workspace
