"""Bounded AES ZIP handling for trusted PostgreSQL dumps."""

import hashlib
import hmac
import json
import stat
import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

import pyzipper

from .configuration import MIN_KEY_BYTES, BackupConfig, BackupError, validate_passphrase

CHUNK = 1024 * 1024
ENTRIES = frozenset({"manifest.json", "manifest.hmac", "database.dump"})
INVALID_ARCHIVE = "Die Sicherung ist ungültig oder nicht vertrauenswürdig."
AES_256 = 3
AES_AE2 = 2
MAGIC = b"PGDMP"
MAX_DIRECTORY_BYTES = 16384
END_RECORD_SIZE = 22


def digest_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()


def write_archive(
    dump: Path,
    destination: Path,
    passphrase: str,
    metadata: dict[str, Any],
    config: BackupConfig,
) -> None:
    key = config.require_key()
    password = validate_passphrase(passphrase)
    size = dump.stat().st_size
    if size > config.max_dump_bytes:
        raise BackupError("Die Datenbank überschreitet die erlaubte Sicherungsgröße.")
    manifest = {
        **metadata,
        "format": "alloq-postgresql-1",
        "created_at": datetime.now(UTC).isoformat(),
        "dump_bytes": size,
        "dump_sha256": digest_file(dump),
    }
    data = _manifest_bytes(manifest)
    if len(data) > MAX_DIRECTORY_BYTES:
        raise BackupError("Die Sicherungsmetadaten überschreiten die erlaubte Größe.")
    with pyzipper.AESZipFile(
        destination, "w", compression=pyzipper.ZIP_STORED, allowZip64=False
    ) as zipped:
        zipped.setpassword(password)
        zipped.setencryption(pyzipper.WZ_AES, nbits=256, force_wz_aes_version=2)
        zipped.writestr("manifest.json", data)
        zipped.writestr("manifest.hmac", hmac.digest(key, data, "sha256"))
        zipped.write(str(dump), "database.dump")
    destination.chmod(0o600)
    if destination.stat().st_size > config.max_archive_bytes:
        raise BackupError("Die Sicherung überschreitet die erlaubte Dateigröße.")


def _copy_bounded(source: BinaryIO, destination: Path, limit: int) -> None:
    size = 0
    with destination.open("xb") as target:
        destination.chmod(0o600)
        while chunk := source.read(CHUNK):
            size += len(chunk)
            if size > limit:
                raise BackupError(INVALID_ARCHIVE)
            target.write(chunk)


def _verify_entries(zipped: Any, config: BackupConfig) -> None:
    infos = zipped.infolist()
    if len(infos) != len(ENTRIES) or {i.filename for i in infos} != ENTRIES:
        raise BackupError(INVALID_ARCHIVE)
    for info in infos:
        limit = config.max_dump_bytes if info.filename == "database.dump" else 16384
        if (
            not info.flag_bits & 1
            or info.wz_aes_strength != AES_256
            or info.wz_aes_version != AES_AE2
            or info.wz_aes_vendor_id != b"AE"
            or info.compress_type not in (pyzipper.ZIP_STORED, pyzipper.ZIP_DEFLATED)
            or stat.S_ISLNK(info.external_attr >> 16)
            or info.file_size > limit
            or info.file_size > max(info.compress_size, 1) * 100
        ):
            raise BackupError(INVALID_ARCHIVE)


def _check_directory(archive: Path, limit: int) -> None:
    """Bound the central directory BEFORE a ZIP library allocates its entries."""
    size = archive.stat().st_size
    if not END_RECORD_SIZE <= size <= limit:
        raise BackupError(INVALID_ARCHIVE)
    with archive.open("rb") as source:
        source.seek(-END_RECORD_SIZE, 2)
        magic, disk, directory_disk, entries, total, length, offset, comment = (
            struct.unpack("<4s4H2LH", source.read(END_RECORD_SIZE))
        )
    if (
        magic != b"PK\x05\x06"
        or disk
        or directory_disk
        or comment
        or entries != len(ENTRIES)
        or total != len(ENTRIES)
        or length > MAX_DIRECTORY_BYTES
        or offset + length != size - END_RECORD_SIZE
    ):
        raise BackupError(INVALID_ARCHIVE)


def read_archive(
    archive: Path,
    destination: Path,
    passphrase: str,
    config: BackupConfig,
) -> dict[str, Any]:
    """Authenticate metadata first, then stream and authenticate the dump."""
    keys = [config.require_key()]
    keys += [k.get_secret_value().encode() for k in config.verification_keys]
    try:
        _check_directory(archive, config.max_archive_bytes)
        with pyzipper.AESZipFile(archive) as zipped:
            zipped.setpassword(validate_passphrase(passphrase))
            _verify_entries(zipped, config)
            data = zipped.read("manifest.json")
            signature = zipped.read("manifest.hmac")
            if not any(
                len(key) >= MIN_KEY_BYTES
                and hmac.compare_digest(hmac.digest(key, data, "sha256"), signature)
                for key in keys
            ):
                raise BackupError(INVALID_ARCHIVE)
            manifest = json.loads(data)
            if (
                not isinstance(manifest, dict)
                or manifest.get("format") != "alloq-postgresql-1"
                or type(manifest.get("dump_bytes")) is not int
                or not len(MAGIC) <= manifest["dump_bytes"] <= config.max_dump_bytes
            ):
                raise BackupError(INVALID_ARCHIVE)
            with zipped.open("database.dump") as source:
                _copy_bounded(source, destination, manifest["dump_bytes"])
        if destination.stat().st_size != manifest["dump_bytes"] or digest_file(
            destination
        ) != manifest.get("dump_sha256"):
            raise BackupError(INVALID_ARCHIVE)
        with destination.open("rb") as dump:
            if dump.read(len(MAGIC)) != MAGIC:
                raise BackupError(INVALID_ARCHIVE)
        return manifest
    except BackupError:
        destination.unlink(missing_ok=True)
        raise
    except ValueError, RuntimeError, OSError, KeyError, pyzipper.BadZipFile:
        destination.unlink(missing_ok=True)
        raise BackupError(INVALID_ARCHIVE) from None
