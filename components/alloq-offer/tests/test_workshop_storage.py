import asyncio

import pytest
from alloq_offer.workshop.storage import (
    BlobNotFoundError,
    BlobTooLargeError,
    DbBlobStore,
)


async def test_put_dedupes_by_content_and_get_returns_bytes(db) -> None:
    store = DbBlobStore(1024, db.session)
    first = await store.put(b"hallo", "text/plain")
    second = await store.put(b"hallo", "text/plain")
    other = await store.put(b"welt", "text/plain")
    assert first == second != other
    assert await store.get(first) == b"hallo"


async def test_size_limit_is_enforced(db) -> None:
    store = DbBlobStore(3, db.session)
    with pytest.raises(BlobTooLargeError):
        await store.put(b"zu lang", "text/plain")


async def test_delete_removes_blob(db) -> None:
    store = DbBlobStore(1024, db.session)
    blob_id = await store.put(b"x", "text/plain")
    await store.delete(blob_id)
    with pytest.raises(BlobNotFoundError):
        await store.get(blob_id)


async def test_concurrent_put_of_same_content_returns_one_id(db) -> None:
    store = DbBlobStore(1024, db.session)
    ids = await asyncio.gather(*(store.put(b"same", "text/plain") for _ in range(4)))
    assert len(set(ids)) == 1
