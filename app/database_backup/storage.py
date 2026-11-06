"""Private workspaces with crash cleanup and live-operation file locks."""

import asyncio
import fcntl
import os
import shutil
import stat
import tempfile
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import anyio

from .configuration import BackupError
from app.configuration import configure

PRIVATE_MODE = 0o700


def private_root() -> Path:
    root = Path(tempfile.gettempdir()) / f"alloq-backups-{os.getuid()}"
    root.mkdir(mode=0o700, exist_ok=True)
    info = root.lstat()
    if (
        root.is_symlink()
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != PRIVATE_MODE
    ):
        raise BackupError("Das private Sicherungsverzeichnis ist nicht sicher.")
    return root


@contextmanager
def private_workspace() -> Generator[Path]:
    with tempfile.TemporaryDirectory(
        prefix="operation-", dir=private_root()
    ) as temporary:
        directory = Path(temporary)
        with (directory / ".active").open("xb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield directory


def cleanup_abandoned(maximum_age: int) -> None:
    root = private_root()
    for directory in root.glob("operation-*"):
        if directory.is_symlink() or not directory.is_dir():
            continue
        if time.time() - directory.stat().st_mtime < maximum_age:
            continue
        try:
            with (directory / ".active").open("ab") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                shutil.rmtree(directory)
        except FileNotFoundError:
            continue


async def backup_cleanup_worker() -> None:
    while True:
        await anyio.to_thread.run_sync(
            cleanup_abandoned, configure().app.database_backup.timeout_seconds * 2 + 60
        )
        await asyncio.sleep(60)
