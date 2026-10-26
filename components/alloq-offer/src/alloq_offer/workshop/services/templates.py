"""Published template versions from the database (spec 6.1).

A version never changes once published, so a loaded package is cached by the id
of its row without invalidation.
"""

import logging

from pydantic import ValidationError
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.entities import BlobEntity
from alloq_offer.workshop.export.template_package import (
    TemplateError,
    TemplatePackage,
)
from alloq_offer.workshop.template_entities import (
    OfferTemplateEntity,
    OfferTemplateVersionEntity,
)

logger = logging.getLogger(__name__)

UNKNOWN_VERSION = "Diese Version der Vorlage gibt es nicht."
BROKEN_VERSION = "Diese Version der Vorlage ist beschädigt."
NO_VERSION = "Die Vorlage hat noch keine veröffentlichte Version."
# Workspaces made before templates lived in the database name version 1 like this.
LEGACY_VERSIONS = {"quo_v1.0": 1}

_cache: dict[int, TemplatePackage] = {}


def version_number(version: str) -> int:
    """The number of a stored version text; legacy texts map to their number."""
    if version in LEGACY_VERSIONS:
        return LEGACY_VERSIONS[version]
    try:
        return int(version)
    except ValueError as exc:
        raise TemplateError(UNKNOWN_VERSION) from exc


def clear_cache() -> None:
    _cache.clear()


async def _package(
    session: AsyncSession, key: str, row: OfferTemplateVersionEntity
) -> TemplatePackage:
    layout = await session.scalar(
        select(BlobEntity.data).where(BlobEntity.id == row.layout_blob_id)
    )
    try:
        if layout is None:
            raise TemplateError(BROKEN_VERSION)
        package = TemplatePackage.model_validate(
            {
                **row.payload,
                "key": key,
                "version": str(row.number),
                "layout_bytes": layout,
            }
        )
        package.check_layout()
    except (ValidationError, TemplateError) as exc:
        logger.warning("Template %s version %s is broken", key, row.number)
        raise TemplateError(BROKEN_VERSION) from exc
    _cache[row.id] = package
    return package


def _version_query(key: str, version: str | int) -> Select:
    number = version if isinstance(version, int) else version_number(version)
    return (
        select(OfferTemplateVersionEntity.id)
        .join(OfferTemplateEntity)
        .where(
            OfferTemplateEntity.key == key,
            OfferTemplateVersionEntity.number == number,
        )
    )


async def template_exists(session: AsyncSession, key: str, version: str) -> bool:
    try:
        return await session.scalar(_version_query(key, version)) is not None
    except TemplateError:
        return False


async def load_template(
    session: AsyncSession, key: str, version: str | int
) -> TemplatePackage:
    """The published version ``version`` of template ``key``."""
    row_id = await session.scalar(_version_query(key, version))
    if row_id is None:
        raise TemplateError(UNKNOWN_VERSION)
    if row_id in _cache:
        return _cache[row_id]
    row = await session.get(OfferTemplateVersionEntity, row_id)
    assert row is not None  # noqa: S101  # found above
    return await _package(session, key, row)


async def latest_template(session: AsyncSession, key: str) -> TemplatePackage:
    """The newest published version of template ``key``."""
    number = await session.scalar(
        select(func.max(OfferTemplateVersionEntity.number))
        .join(OfferTemplateEntity)
        .where(OfferTemplateEntity.key == key)
    )
    if number is None:
        raise TemplateError(NO_VERSION)
    return await load_template(session, key, number)
