"""The HTTP route that serves the pictures of image chapters."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import httpx
from alloq_offer.workshop import image_api
from alloq_offer.workshop.entities import ChapterEntity, ChapterRevisionEntity
from alloq_offer.workshop.storage import DbBlobStore
from fastapi import FastAPI
from sqlalchemy import select
from test_chapter_state_helpers import as_editor as _as_editor
from test_chapter_state_helpers import run as _run
from test_workshop_images import PNG, _file, _with_image

from appkit_user.authentication.http_guard import require_session

JPEG = b"\xff\xd8\xff\xe0" + b"\x01" * 20


def _signed_in() -> MagicMock:
    """Any signed-in user; offers are readable by all of them."""
    return MagicMock(is_admin=False, user_id=2, roles=[])


@asynccontextmanager
async def _client(db, *, signed_in: bool = True) -> AsyncIterator[httpx.AsyncClient]:  # noqa: ANN001
    api = FastAPI()
    api.include_router(image_api.router)
    if signed_in:
        api.dependency_overrides[require_session] = _signed_in
    transport = httpx.ASGITransport(app=api)
    with patch.object(image_api, "get_asyncdb_session", db.session):
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            yield c


async def _uploaded(db, data: bytes = PNG) -> int:  # noqa: ANN001
    state, _ = await _with_image(db)
    with _as_editor(state, db):
        await _run(state.upload_image, [_file(data)])
    return state.active["blob_id"]


async def _point_image_at(db, blob_id: int) -> None:  # noqa: ANN001
    """Make the current revision of the image chapter name ``blob_id``."""
    async with db.session() as session:
        chapter = await session.scalar(
            select(ChapterEntity).where(ChapterEntity.chapter_type == "image")
        )
        assert chapter is not None
        revision = await session.scalar(
            select(ChapterRevisionEntity).where(
                ChapterRevisionEntity.chapter_id == chapter.id,
                ChapterRevisionEntity.number == chapter.revision,
            )
        )
        assert revision is not None
        revision.content = {**revision.content, "blob_id": blob_id}


def test_the_url_names_offer_and_blob() -> None:
    assert image_api.image_path(3, 7) == "/api/offers/3/images/7"


async def test_serves_a_referenced_picture_with_strict_headers(db) -> None:  # noqa: ANN001
    blob_id = await _uploaded(db)
    async with _client(db) as client:
        response = await client.get(image_api.image_path(1, blob_id))
    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == image_api.CSP
    assert response.headers["cache-control"].startswith("private")


async def test_refuses_anonymous_requests(db) -> None:  # noqa: ANN001
    blob_id = await _uploaded(db)
    async with _client(db, signed_in=False) as client:
        response = await client.get(image_api.image_path(1, blob_id))
    assert response.status_code == 401


async def test_refuses_pictures_of_other_offers(db) -> None:  # noqa: ANN001
    blob_id = await _uploaded(db)
    async with _client(db) as client:
        response = await client.get(image_api.image_path(2, blob_id))
    assert response.status_code == 404


async def test_refuses_pictures_no_current_revision_shows(db) -> None:  # noqa: ANN001
    old = await _uploaded(db)
    blob_id = await DbBlobStore(10**7, db.session).put(JPEG, "image/jpeg")
    await _point_image_at(db, blob_id)
    async with _client(db) as client:
        assert (await client.get(image_api.image_path(1, old))).status_code == 404
        current = await client.get(image_api.image_path(1, blob_id))
    assert current.headers["content-type"] == "image/jpeg"


async def test_refuses_blobs_that_are_no_picture(db) -> None:  # noqa: ANN001
    await _uploaded(db)
    blob_id = await DbBlobStore(10**7, db.session).put(b"%PDF-1.7", "image/png")
    await _point_image_at(db, blob_id)
    async with _client(db) as client:
        response = await client.get(image_api.image_path(1, blob_id))
    assert response.status_code == 404


async def test_refuses_pictures_of_removed_chapters(db) -> None:  # noqa: ANN001
    state, _ = await _with_image(db)
    with _as_editor(state, db):
        await _run(state.upload_image, [_file(PNG)])
        blob_id = state.active["blob_id"]
        await _run(state.remove_active)
    async with _client(db) as client:
        response = await client.get(image_api.image_path(1, blob_id))
    assert response.status_code == 404
