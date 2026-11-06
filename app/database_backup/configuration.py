"""Host configuration and external trust settings for database backups."""

from pydantic import Field, SecretStr

from appkit_commons.configuration.base import BaseConfig

MIN_KEY_BYTES = 32
MIN_PASSPHRASE = 24
MAX_PASSPHRASE = 256
MIN_DISTINCT_CHARACTERS = 8


class BackupError(Exception):
    """A safe, user-facing failure without database/tool/credential details."""


class BackupConfig(BaseConfig):
    enabled: bool = False
    signing_key: SecretStr = SecretStr("")
    verification_keys: list[SecretStr] = Field(default_factory=list)
    max_archive_bytes: int = Field(default=536870912, ge=1024, le=2147483647)
    max_dump_bytes: int = Field(default=1073741824, ge=1024, le=1073741824)
    timeout_seconds: int = Field(default=300, ge=10, le=1800)
    lock_timeout_seconds: int = Field(default=30, ge=1, le=120)
    max_password_attempts: int = Field(default=5, ge=1, le=10)

    def require_key(self) -> bytes:
        """Never allow unsigned backups, even with an explicit enable flag."""
        key = self.signing_key.get_secret_value().encode()
        if len(key) < MIN_KEY_BYTES:
            raise BackupError("Der Sicherungsschlüssel ist nicht konfiguriert.")
        return key


def validate_passphrase(passphrase: str) -> bytes:
    """Require a long separate phrase; the UI generates 192 random bits."""
    if (
        not MIN_PASSPHRASE <= len(passphrase) <= MAX_PASSPHRASE
        or len(set(passphrase)) < MIN_DISTINCT_CHARACTERS
        or passphrase.isspace()
    ):
        raise BackupError(
            "Verwenden Sie 24 bis 256 Zeichen und mindestens acht verschiedene Zeichen."
        )
    return passphrase.encode("utf-8")
