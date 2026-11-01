"""Pictures of image chapters: which files count as images, and which picture
an offer may show.

The type comes from the first bytes, never from the file name or the browser.
Only PNG and JPEG pass; SVG could carry scripts.
"""

import logging

from sqlalchemy import select

from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    BlobEntity,
    ChapterEntity,
    ChapterRevisionEntity,
)

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 3 * 1024 * 1024
SIGNATURES = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}
NOT_AN_IMAGE = "Bitte laden Sie ein Bild als PNG oder JPEG hoch."
TOO_LARGE = "Ein Bild darf höchstens 3 MB groß sein."


class ImageError(ValueError):
    """The file is no usable picture; the message is German."""


def image_mime(data: bytes) -> str | None:
    return next(
        (mime for magic, mime in SIGNATURES.items() if data.startswith(magic)), None
    )


def check_image(data: bytes) -> str:
    """The MIME type of an uploaded picture; raise ``ImageError`` otherwise."""
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageError(TOO_LARGE)
    mime = image_mime(data)
    if mime is None:
        raise ImageError(NOT_AN_IMAGE)
    return mime


async def offer_image(
    session_factory: SessionFactory, offer_id: int, blob_id: int
) -> tuple[bytes, str] | None:
    """The picture and its MIME type when a live image chapter of the offer shows
    it in its current revision; ``None`` otherwise, also for non-pictures."""
    async with session_factory() as session:
        contents = await session.scalars(
            select(ChapterRevisionEntity.content)
            .join(ChapterEntity, ChapterEntity.id == ChapterRevisionEntity.chapter_id)
            .where(
                ChapterEntity.offer_id == offer_id,
                ChapterEntity.chapter_type == "image",
                ChapterEntity.removed_at.is_(None),
                ChapterRevisionEntity.number == ChapterEntity.revision,
            )
        )
        if not any(c.get("blob_id") == blob_id for c in contents.all()):
            return None
        data = await session.scalar(
            select(BlobEntity.data).where(BlobEntity.id == blob_id)
        )
    if data is None:
        logger.warning("Image blob %s is missing", blob_id)
        return None
    mime = image_mime(data)
    return None if mime is None else (data, mime)
