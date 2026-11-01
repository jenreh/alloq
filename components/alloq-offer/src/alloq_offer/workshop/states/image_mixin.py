"""Image and table chapters: upload, picture settings and the caption below.

A mixin of ``ChapterState``; edits store a revision through ``_save_content``.
The browser loads the pictures from the authorised route in ``image_api``.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.workshop.content.schema import (
    MAX_ALT,
    MAX_IMAGE_WIDTH,
    MIN_IMAGE_WIDTH,
    ImageContent,
    Run,
    TableContent,
)
from alloq_offer.workshop.content.text import Content
from alloq_offer.workshop.services import images
from alloq_offer.workshop.states.helpers import browser_int
from alloq_offer.workshop.storage import BlobStore, BlobTooLargeError

MAX_CAPTION = 500
UPLOAD_ID = "aq-image-upload"
WIDTH_OPTIONS: list[dict[str, str]] = [
    {"value": "33", "label": "Klein"},
    {"value": "50", "label": "Mittel"},
    {"value": "75", "label": "Groß"},
    {"value": "100", "label": "Volle Breite"},
]
ALIGN_OPTIONS: list[dict[str, str]] = [
    {"value": "left", "label": "Links"},
    {"value": "center", "label": "Mitte"},
    {"value": "right", "label": "Rechts"},
]


class ImageMixin(rx.State, mixin=True):
    """Pictures of image chapters and captions of image and table chapters."""

    if TYPE_CHECKING:
        active_key: str
        _content: dict[str, Any]

        async def _save_content(self, content: Content) -> Any | None: ...

        def _blob_store(self) -> BlobStore: ...

    def _image(self) -> ImageContent | None:
        if self._content.get("chapter_type") != "image":
            return None
        return ImageContent.model_validate(self._content)

    async def _store_image(self, change: dict[str, Any]) -> Any | None:
        image = self._image()
        if image is None:
            return None
        return await self._save_content(image.model_copy(update=change))

    @rx.event
    @requires_offer_editor
    async def upload_image(self, files: list[rx.UploadFile]) -> AsyncGenerator[Any]:
        """The picked, dropped or pasted picture of the selected image chapter."""
        if not files or self._image() is None:
            return
        file = files[0]
        try:
            if file.size is not None and file.size > images.MAX_IMAGE_BYTES:
                raise images.ImageError(images.TOO_LARGE)
            data = await file.read()
            mime = images.check_image(data)
            blob_id = await self._blob_store().put(data, mime)
        except images.ImageError as exc:
            yield rx.toast.error(str(exc), position="top-right")
            return
        except BlobTooLargeError:
            yield rx.toast.error(images.TOO_LARGE, position="top-right")
            return
        yield await self._store_image({"blob_id": blob_id})
        yield rx.clear_selected_files(UPLOAD_ID)

    @rx.event
    @requires_offer_editor
    async def set_image_alt(self, text: str) -> AsyncGenerator[Any]:
        image = self._image()
        alt = str(text).strip()[:MAX_ALT]
        if image is not None and alt != image.alt:
            yield await self._store_image({"alt": alt})

    @rx.event
    @requires_offer_editor
    async def set_image_width(self, value: str | int) -> AsyncGenerator[Any]:
        image, width = self._image(), browser_int(value)
        if (
            image is None
            or width is None
            or not MIN_IMAGE_WIDTH <= width <= MAX_IMAGE_WIDTH
        ):
            return
        if width != image.width:
            yield await self._store_image({"width": width})

    @rx.event
    @requires_offer_editor
    async def set_image_align(self, value: str) -> AsyncGenerator[Any]:
        image = self._image()
        if image is None or value not in {o["value"] for o in ALIGN_OPTIONS}:
            return
        if value != image.align:
            yield await self._store_image({"align": value})

    @rx.event
    @requires_offer_editor
    async def set_caption(self, text: str) -> AsyncGenerator[Any]:
        """The description below an image or table chapter."""
        kind = self._content.get("chapter_type")
        model = {"image": ImageContent, "table": TableContent}.get(str(kind))
        if model is None:
            return
        content = model.model_validate(self._content)
        caption = str(text).strip()[:MAX_CAPTION]
        description = [Run(text=caption)] if caption else []
        if description != content.description:
            yield await self._save_content(
                content.model_copy(update={"description": description})
            )
