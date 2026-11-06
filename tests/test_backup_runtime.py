"""Whole-operation leases and fresh auth caches survive restore boundaries."""

import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from app.database_backup import runtime, storage


def test_appkit_cache_descriptors_exist_on_real_states() -> None:
    assert {
        "authenticated_user",
        "is_authenticated",
    } <= runtime.UserSession.computed_vars.keys()


async def test_auth_cache_invalidated_on_every_event() -> None:
    sessions = [
        SimpleNamespace(
            _session_expires_at=object(),
            computed_vars={
                "authenticated_user": MagicMock(),
                "is_authenticated": MagicMock(),
            },
        )
        for _ in range(1)
    ]
    state = SimpleNamespace(get_state=AsyncMock(side_effect=sessions))
    with patch.object(
        runtime.SessionFilter, "preprocess", AsyncMock(return_value=None)
    ):
        await runtime.BackupSessionFilter().preprocess(MagicMock(), state, MagicMock())
    for session in sessions:
        assert session._session_expires_at is None
        session.computed_vars["authenticated_user"].mark_dirty.assert_called_once_with(
            instance=session
        )
        session.computed_vars["is_authenticated"].mark_dirty.assert_called_once_with(
            instance=session
        )


async def test_real_appkit_state_cache_can_be_invalidated() -> None:
    session = runtime.UserSession()
    state = SimpleNamespace(get_state=AsyncMock(return_value=session))
    with patch.object(
        runtime.SessionFilter, "preprocess", AsyncMock(return_value=None)
    ):
        await runtime.BackupSessionFilter().preprocess(MagicMock(), state, MagicMock())
    assert session._session_expires_at is None


async def test_processor_lifespan_uses_guarded_processor() -> None:
    @asynccontextmanager
    async def configured(**_kwargs: Any) -> AsyncGenerator[None]:
        yield

    processor = SimpleNamespace(configure=configured)
    app = SimpleNamespace(
        event_namespace=None, backend_exception_handler=None, state_manager=object()
    )
    with patch.object(runtime, "BackupEventProcessor", return_value=processor):
        async with runtime.BackupApp._setup_event_processor(app):
            assert app._event_processor is processor


async def test_workshop_worker_uses_activity_runner() -> None:
    config = SimpleNamespace(worker_enabled=True)
    registry = SimpleNamespace(get=lambda _kind: config)
    runner = SimpleNamespace(run_forever=AsyncMock())
    with (
        patch.object(runtime, "service_registry", return_value=registry),
        patch.object(runtime, "BackupJobRunner", return_value=runner),
    ):
        await runtime.backup_aware_worker()
    runner.run_forever.assert_awaited_once()


async def test_entire_event_runs_inside_activity_lease() -> None:
    events = []

    @asynccontextmanager
    async def lease() -> AsyncGenerator[None]:
        events.append("acquired")
        try:
            yield
        finally:
            events.append("released")

    async def execute(_self: Any, **_kwargs: Any) -> None:
        assert events == ["acquired"]
        events.append("executed")

    with (
        patch.object(runtime, "application_activity", lease),
        patch.object(runtime.BaseStateEventProcessor, "_execute_event", execute),
    ):
        processor = runtime.BackupEventProcessor()
        await processor._execute_event(
            entry=MagicMock(), registered_handler=MagicMock()
        )
    assert events == ["acquired", "executed", "released"]


def test_abandoned_files_cleaned_but_active_workspace_preserved(
    tmp_path: Path,
) -> None:
    with patch.object(storage, "private_root", return_value=tmp_path):
        abandoned = tmp_path / "operation-abandoned"
        abandoned.mkdir()
        (abandoned / "database.dump").write_bytes(b"sensitive")
        stale = time.time() - 1000
        os.utime(abandoned, (stale, stale))
        with storage.private_workspace() as active:
            os.utime(active, (stale, stale))
            storage.cleanup_abandoned(300)
            assert active.exists()
            assert not abandoned.exists()
        assert not active.exists()
