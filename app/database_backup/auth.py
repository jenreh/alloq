"""Fresh session checks and durable per-action password throttling."""

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Any

import anyio
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from appkit_commons.security import check_password_hash

from .configuration import BackupConfig, BackupError

DENIED = "Keine Berechtigung oder ungültiges Passwort."
MAX_PASSWORD_LENGTH = 1024


@dataclass(frozen=True)
class PasswordProof:
    user_id: int
    password_hash: str = field(repr=False)


async def current_user(connection: AsyncConnection, session_id: str) -> dict[str, Any]:
    async with connection.cursor(row_factory=dict_row) as cursor:
        await cursor.execute(
            "SELECT u.id, u.email, u._password, u.is_active, u.is_verified, "
            "u.needs_password_reset, u.is_admin, u.roles "
            "FROM public.auth_users u JOIN public.auth_sessions s ON s.user_id=u.id "
            "WHERE s.session_id=%s AND s.expires_at > CURRENT_TIMESTAMP",
            (session_id,),
        )
        user = await cursor.fetchone()
    if (
        not user
        or not user["is_active"]
        or not user["is_verified"]
        or not user["is_admin"]
        or "database_backup" not in (user["roles"] or [])
        or user["needs_password_reset"]
    ):
        raise BackupError(DENIED)
    return user


async def verify_password(
    connection: AsyncConnection,
    session_id: str,
    password: str,
    config: BackupConfig,
) -> PasswordProof:
    """Count attempts before expensive verification; success only authorizes this call.

    Commit failure counters before raising. A per-user transaction lock prevents
    parallel workers from opening independent password-guess windows.
    """
    valid = False
    async with connection.transaction():
        user = await current_user(connection, session_id)
        key = hashlib.sha256(f"backup-password:{user['id']}".encode()).hexdigest()
        lock = int(key[:15], 16)
        await connection.execute("SELECT pg_advisory_xact_lock(%s)", (lock,))
        user = await current_user(connection, session_id)
        cursor = await connection.execute(
            "INSERT INTO public.auth_login_throttle "
            "(key, failures, window_started_at) VALUES (%s, 1, CURRENT_TIMESTAMP) "
            "ON CONFLICT (key) DO UPDATE SET "
            "failures = CASE WHEN auth_login_throttle.window_started_at "
            "< CURRENT_TIMESTAMP - INTERVAL '15 minutes' THEN 1 "
            "ELSE auth_login_throttle.failures + 1 END, "
            "window_started_at = CASE WHEN auth_login_throttle.window_started_at "
            "< CURRENT_TIMESTAMP - INTERVAL '15 minutes' THEN CURRENT_TIMESTAMP "
            "ELSE auth_login_throttle.window_started_at END RETURNING failures",
            (key,),
        )
        row = await cursor.fetchone()
        if (
            row is not None
            and row[0] <= config.max_password_attempts
            and user["_password"]
            and 0 < len(password) <= MAX_PASSWORD_LENGTH
        ):
            valid = await anyio.to_thread.run_sync(
                check_password_hash, user["_password"], password
            )
        if valid:
            await connection.execute(
                "DELETE FROM public.auth_login_throttle WHERE key=%s", (key,)
            )
    if not valid:
        raise BackupError(DENIED)
    return PasswordProof(user["id"], user["_password"])


async def verified_user(
    connection: AsyncConnection, session_id: str, proof: PasswordProof
) -> dict[str, Any]:
    user = await current_user(connection, session_id)
    if user["id"] != proof.user_id or not hmac.compare_digest(
        user["_password"] or "", proof.password_hash
    ):
        raise BackupError(DENIED)
    return user
