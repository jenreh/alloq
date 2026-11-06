"""Drain complete events/jobs and discard authentication caches before each event.

The small processor/App overrides mirror the pinned Reflex 0.10.1 lifecycle.
They cover async background handlers too, which outlive middleware postprocess.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache

import reflex as rx
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.jobs.registry import JobContext
from alloq_offer.workshop.jobs.runner import JobRunner
from psycopg_pool import AsyncConnectionPool
from reflex.state import BaseState, StateUpdate
from reflex_base.event import Event
from reflex_base.event.processor import BaseStateEventProcessor
from reflex_base.event.processor.event_processor import EventQueueEntry
from reflex_base.registry import RegisteredEventHandler

from appkit_commons.database.configuration import DatabaseConfig
from appkit_commons.registry import service_registry
from appkit_user.authentication.session_filter import SessionFilter
from appkit_user.authentication.states import UserSession

from .configuration import BackupError
from .maintenance import MAINTENANCE_LOCK
from .postgres import connection_parameters


@lru_cache(maxsize=1)
def activity_pool() -> AsyncConnectionPool:
    database = service_registry().get(DatabaseConfig)
    return AsyncConnectionPool(
        kwargs={**connection_parameters(database), "autocommit": True},
        min_size=0,
        max_size=8,
        max_waiting=16,
        timeout=10,
        open=False,
        name="alloq-activity",
    )


@asynccontextmanager
async def application_activity() -> AsyncGenerator[None]:
    """A dedicated bounded pool prevents inner app transactions exhausting leases."""
    database = service_registry().get(DatabaseConfig)
    if database.type != "postgresql":
        yield
        return
    pool = activity_pool()
    await pool.open()
    async with pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT pg_try_advisory_lock_shared(%s)", (MAINTENANCE_LOCK,)
        )
        row = await cursor.fetchone()
        if not row or not row[0]:
            raise BackupError("Die Datenbank wird gerade wiederhergestellt.")
        try:
            yield
        finally:
            try:
                await connection.execute(
                    "SELECT pg_advisory_unlock_shared(%s)", (MAINTENANCE_LOCK,)
                )
            except BaseException:
                await connection.close()
                raise


class BackupSessionFilter(SessionFilter):
    async def preprocess(
        self, app: rx.App, state: BaseState, event: Event
    ) -> StateUpdate | None:
        session = await state.get_state(UserSession)
        session._session_expires_at = None  # noqa: SLF001 - owning appkit state
        for name in ("authenticated_user", "is_authenticated"):
            session.computed_vars[name].mark_dirty(instance=session)
        return await super().preprocess(app, state, event)


class BackupEventProcessor(BaseStateEventProcessor):
    async def _execute_event(
        self, *, entry: EventQueueEntry, registered_handler: RegisteredEventHandler
    ) -> None:
        async with application_activity():
            await super()._execute_event(
                entry=entry, registered_handler=registered_handler
            )


class BackupApp(rx.App):
    @asynccontextmanager
    async def _setup_event_processor(self) -> AsyncGenerator[None]:
        if self.event_namespace is not None:
            self.event_namespace._token_manager._reset_instance_id()  # noqa: SLF001
        self._event_processor = BackupEventProcessor(
            middleware=self, backend_exception_handler=self.backend_exception_handler
        )
        async with self._event_processor.configure(
            state_manager=self.state_manager, event_namespace=self.event_namespace
        ):
            try:
                yield
            finally:
                if activity_pool.cache_info().currsize:
                    await activity_pool().close()
                    activity_pool.cache_clear()


class BackupJobRunner(JobRunner):
    async def _execute(self, context: JobContext) -> None:
        async with application_activity():
            await super()._execute(context)


async def backup_aware_worker() -> None:
    config = service_registry().get(WorkshopConfig)
    if config.worker_enabled:
        await BackupJobRunner(config).run_forever()
