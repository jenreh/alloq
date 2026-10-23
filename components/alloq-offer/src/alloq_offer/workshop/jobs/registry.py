"""Job handlers by kind."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


class TransientJobError(RuntimeError):
    """The job may succeed on a later attempt (timeout, rate limit)."""


class UnknownJobKindError(LookupError):
    """No handler is registered for the job kind."""


@dataclass(frozen=True)
class JobContext:
    """What a handler gets to know about the job it runs."""

    job_id: int
    offer_id: int
    kind: str
    payload: dict = field(default_factory=dict)
    input_revisions: dict = field(default_factory=dict)
    attempt: int = 1


JobHandler = Callable[[JobContext], Awaitable[dict | None]]

_HANDLERS: dict[str, JobHandler] = {}


def register_handler(kind: str) -> Callable[[JobHandler], JobHandler]:
    """Register ``handler`` for ``kind``; re-registering replaces it."""

    def decorator(handler: JobHandler) -> JobHandler:
        _HANDLERS[kind] = handler
        return handler

    return decorator


def get_handler(kind: str) -> JobHandler:
    try:
        return _HANDLERS[kind]
    except KeyError as exc:
        raise UnknownJobKindError(kind) from exc


def registered_kinds() -> list[str]:
    return sorted(_HANDLERS)
