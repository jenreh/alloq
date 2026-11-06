"""Database transaction locks coordinate Alloq workers and replicas."""

from sqlalchemy import Engine, event
from sqlalchemy.engine import Connection

from .configuration import BackupError

MAINTENANCE_LOCK = 68491253001
OPERATION_LOCK = 68491253002


def guard_transaction(connection: Connection) -> None:
    """Every application DB transaction participates, including background jobs.

    A waiting restore drains transactions holding the shared lock. New requests
    fail closed rather than queue queries against schemas being replaced. Raw
    backup connections deliberately do not use SQLAlchemy's application engines.
    """
    if connection.dialect.name != "postgresql":
        return
    available = connection.exec_driver_sql(
        "SELECT pg_try_advisory_xact_lock_shared(%s)", (MAINTENANCE_LOCK,)
    ).scalar()
    if not available:
        raise BackupError("Die Datenbank wird gerade wiederhergestellt.")


def install_maintenance_guard() -> None:
    if not event.contains(Engine, "begin", guard_transaction):
        event.listen(Engine, "begin", guard_transaction)
