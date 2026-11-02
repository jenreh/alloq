"""File storage behind a port; the first adapter keeps bytes in Postgres."""

import hashlib
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import BlobEntity
from appkit_commons.database.session import get_asyncdb_session


class BlobTooLargeError(ValueError):
    """The file exceeds the configured size limit."""


class _Readable(Protocol):
    async def read(self, size: int = -1, /) -> bytes: ...


async def read_limited(file: _Readable, max_bytes: int) -> bytes:
    """Read an upload, but never more than ``max_bytes`` into memory.

    The size a client reports can be wrong, so the limit is enforced while
    reading. Raises ``BlobTooLargeError`` when the file is larger.
    """
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise BlobTooLargeError(len(data))
    return data


class BlobNotFoundError(LookupError):
    """No blob with this id."""


class BlobStore(Protocol):
    """Stores file content and hands back a stable blob id."""

    async def put(self, data: bytes, mime: str) -> int: ...

    async def get(self, blob_id: int) -> bytes: ...

    async def get_many(self, blob_ids: list[int]) -> dict[int, bytes]: ...

    async def delete(self, blob_id: int) -> None: ...


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class DbBlobStore:
    """Blobs in ``offer_blobs``, stored once per SHA-256."""

    def __init__(
        self,
        max_bytes: int,
        session_factory: SessionFactory = get_asyncdb_session,
    ) -> None:
        self._max_bytes = max_bytes
        self._session_factory = session_factory

    async def put(self, data: bytes, mime: str) -> int:
        if len(data) > self._max_bytes:
            raise BlobTooLargeError(len(data))
        digest = sha256_hex(data)
        async with self._session_factory() as session:
            existing = await session.scalar(
                select(BlobEntity.id).where(BlobEntity.sha256 == digest)
            )
            if existing is not None:
                return existing
            blob = BlobEntity(sha256=digest, size=len(data), mime=mime, data=data)
            try:
                async with session.begin_nested():
                    session.add(blob)
            except IntegrityError:
                # A concurrent upload of the same content won the race.
                found = await session.scalar(
                    select(BlobEntity.id).where(BlobEntity.sha256 == digest)
                )
                if found is None:
                    raise
                return found
            return blob.id

    async def get(self, blob_id: int) -> bytes:
        async with self._session_factory() as session:
            data = await session.scalar(
                select(BlobEntity.data).where(BlobEntity.id == blob_id)
            )
        if data is None:
            raise BlobNotFoundError(blob_id)
        return data

    async def get_many(self, blob_ids: list[int]) -> dict[int, bytes]:
        """Several blobs in one query; missing ids are left out."""
        if not blob_ids:
            return {}
        async with self._session_factory() as session:
            rows = await session.execute(
                select(BlobEntity.id, BlobEntity.data).where(
                    BlobEntity.id.in_(blob_ids)
                )
            )
            return {row.id: row.data for row in rows}

    async def delete(self, blob_id: int) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(BlobEntity).where(BlobEntity.id == blob_id))
