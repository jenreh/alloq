import asyncio

import pytest
from alloq_offer.workshop.storage import (
    BlobNotFoundError,
    BlobTooLargeError,
    DbBlobStore,
    read_limited,
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


class _Upload:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.asked: list[int] = []

    async def read(self, size: int = -1, /) -> bytes:
        self.asked.append(size)
        return self.data if size < 0 else self.data[:size]


async def test_read_limited_returns_a_file_within_the_limit() -> None:
    assert await read_limited(_Upload(b"abc"), 3) == b"abc"


async def test_read_limited_never_reads_more_than_one_byte_over() -> None:
    upload = _Upload(b"x" * 1000)

    with pytest.raises(BlobTooLargeError):
        await read_limited(upload, 10)

    assert upload.asked == [11]
