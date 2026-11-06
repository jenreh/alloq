"""Encrypted archives must authenticate origin before a dump can be restored."""

import secrets
from pathlib import Path
from unittest.mock import patch

import pytest
import pyzipper
from pydantic import SecretStr

from app.database_backup.archive import read_archive, write_archive
from app.database_backup.configuration import BackupConfig, BackupError

PASSPHRASE = secrets.token_urlsafe(24)


@pytest.fixture
def backup_config() -> BackupConfig:
    return BackupConfig(signing_key=SecretStr("k" * 64), max_dump_bytes=4096)


def test_encrypted_signed_round_trip(
    tmp_path: Path, backup_config: BackupConfig
) -> None:
    dump = tmp_path / "source.dump"
    dump.write_bytes(b"PGDMP" + b"database-data" * 20)
    archive = tmp_path / "backup.zip"
    metadata = {"revision": "head", "key_id": "fingerprint", "server_major": 16}
    write_archive(dump, archive, PASSPHRASE, metadata, backup_config)
    with pyzipper.AESZipFile(archive) as zipped:
        assert all(info.wz_aes_strength == 3 for info in zipped.infolist())
        with pytest.raises(RuntimeError):
            zipped.read("database.dump")
    target = tmp_path / "restored.dump"
    manifest = read_archive(archive, target, PASSPHRASE, backup_config)
    assert manifest["revision"] == "head"
    assert target.read_bytes() == dump.read_bytes()


@pytest.mark.parametrize("password", ["", "wrong-passphrase-with-enough-length"])
def test_wrong_passphrase_is_safe(
    tmp_path: Path, backup_config: BackupConfig, password: str
) -> None:
    dump = tmp_path / "source"
    dump.write_bytes(b"PGDMPcontent")
    archive = tmp_path / "backup.zip"
    write_archive(dump, archive, PASSPHRASE, {}, backup_config)
    with pytest.raises(BackupError):
        read_archive(archive, tmp_path / "out", password, backup_config)


def test_different_signing_key_rejected(
    tmp_path: Path, backup_config: BackupConfig
) -> None:
    dump = tmp_path / "source"
    dump.write_bytes(b"PGDMPcontent")
    archive = tmp_path / "backup.zip"
    write_archive(dump, archive, PASSPHRASE, {}, backup_config)
    other = BackupConfig(signing_key=SecretStr("x" * 64))
    with pytest.raises(BackupError):
        read_archive(archive, tmp_path / "out", PASSPHRASE, other)


@pytest.mark.parametrize("name", ["database.dump", "../database.dump", "nested.zip"])
def test_plain_or_unexpected_archive_is_rejected(
    tmp_path: Path, backup_config: BackupConfig, name: str
) -> None:
    archive = tmp_path / "bad.zip"
    with pyzipper.AESZipFile(archive, "w") as zipped:
        zipped.writestr(name, b"PGDMPcontent")
    with pytest.raises(BackupError):
        read_archive(archive, tmp_path / "out", PASSPHRASE, backup_config)


def test_no_signing_key_fails_closed(tmp_path: Path) -> None:
    dump = tmp_path / "source"
    dump.write_bytes(b"PGDMPcontent")
    with pytest.raises(BackupError):
        write_archive(dump, tmp_path / "out.zip", PASSPHRASE, {}, BackupConfig())


def test_dump_size_limit(tmp_path: Path, backup_config: BackupConfig) -> None:
    dump = tmp_path / "source"
    dump.write_bytes(b"PGDMP" + b"a" * 5000)
    with pytest.raises(BackupError):
        write_archive(dump, tmp_path / "out.zip", PASSPHRASE, {}, backup_config)


@pytest.mark.parametrize("member", ["database.dump", "manifest.json"])
def test_modified_encrypted_archive_rejected_and_dump_removed(
    tmp_path: Path, backup_config: BackupConfig, member: str
) -> None:
    dump = tmp_path / "source"
    dump.write_bytes(b"PGDMPcontent")
    original, tampered = tmp_path / "original.zip", tmp_path / "tampered.zip"
    write_archive(dump, original, PASSPHRASE, {}, backup_config)
    with pyzipper.AESZipFile(original) as source:
        source.setpassword(PASSPHRASE.encode())
        contents = {
            info.filename: source.read(info.filename) for info in source.infolist()
        }
    contents[member] += b"tampered"
    with pyzipper.AESZipFile(tampered, "w", encryption=pyzipper.WZ_AES) as target:
        target.setpassword(PASSPHRASE.encode())
        for name, data in contents.items():
            target.writestr(name, data)
    restored = tmp_path / "restored"
    with pytest.raises(BackupError):
        read_archive(tampered, restored, PASSPHRASE, backup_config)
    assert not restored.exists()


def test_signing_key_rotation(tmp_path: Path, backup_config: BackupConfig) -> None:
    dump = tmp_path / "source"
    dump.write_bytes(b"PGDMPcontent")
    archive = tmp_path / "backup.zip"
    write_archive(dump, archive, PASSPHRASE, {}, backup_config)
    rotated = BackupConfig(
        signing_key=SecretStr("new-key-" + "n" * 50),
        verification_keys=[backup_config.signing_key],
    )
    read_archive(archive, tmp_path / "out", PASSPHRASE, rotated)


@pytest.mark.parametrize("phrase", [" " * 32, "a" * 32, "too-short"])
def test_weak_custom_passphrases_rejected(
    tmp_path: Path, backup_config: BackupConfig, phrase: str
) -> None:
    dump = tmp_path / "source"
    dump.write_bytes(b"PGDMPcontent")
    with pytest.raises(BackupError):
        write_archive(dump, tmp_path / "backup.zip", phrase, {}, backup_config)


def test_large_directory_rejected_before_zip_parser_allocation(
    tmp_path: Path,
    backup_config: BackupConfig,
) -> None:
    archive = tmp_path / "many-entries.zip"
    with pyzipper.AESZipFile(archive, "w") as zipped:
        for index in range(100):
            zipped.writestr(str(index), b"x")
    with patch("app.database_backup.archive.pyzipper.AESZipFile") as parser:
        with pytest.raises(BackupError):
            read_archive(archive, tmp_path / "out", PASSPHRASE, backup_config)
        parser.assert_not_called()
