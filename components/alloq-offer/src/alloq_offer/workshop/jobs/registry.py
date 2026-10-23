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
    max_attempts: int = 1


JobHandler = Callable[[JobContext], Awaitable[dict | None]]
ExhaustedHook = Callable[[JobContext], Awaitable[None]]

_HANDLERS: dict[str, JobHandler] = {}
_EXHAUSTED: dict[str, ExhaustedHook] = {}


def register_handler(
    kind: str, on_exhausted: ExhaustedHook | None = None
) -> Callable[[JobHandler], JobHandler]:
    """Register ``handler`` for ``kind``; re-registering replaces it.

    ``on_exhausted`` runs once when the job failed for good (no attempts left, a
    permanent error or an expired lease), so the handler's data never stays in a
    "running" state.
    """

    def decorator(handler: JobHandler) -> JobHandler:
        _HANDLERS[kind] = handler
        if on_exhausted is None:
            _EXHAUSTED.pop(kind, None)
        else:
            _EXHAUSTED[kind] = on_exhausted
        return handler

    return decorator


def get_exhausted_hook(kind: str) -> ExhaustedHook | None:
    return _EXHAUSTED.get(kind)


def get_handler(kind: str) -> JobHandler:
    try:
        return _HANDLERS[kind]
    except KeyError as exc:
        raise UnknownJobKindError(kind) from exc


def registered_kinds() -> list[str]:
    return sorted(_HANDLERS)
