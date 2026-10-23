"""Access levels of the alloq roles.

Roles add up, and only roles grant access: the admin switch opens just the
administration (``@requires_admin``). The employee role reads projects and
planning; the project manager role edits them and opens dashboard and team, so
a project manager needs the employee role on top. Every signed-in user may
read the offers; only the offer editor role may change them.
"""

import inspect
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, Final

import reflex as rx

import appkit_mantine as mn
from alloq_commons.roles import EMPLOYEE_ROLE, OFFER_EDITOR_ROLE, PROJECT_MANAGER_ROLE
from appkit_commons.roles import Role
from appkit_user.authentication.backend.models import User
from appkit_user.authentication.components.components import requires_role
from appkit_user.authentication.states import LoginState, UserSession

logger = logging.getLogger(__name__)

_NOT_AUTHORIZED_MSG: Final = "Sie haben keine Berechtigung für diese Aktion."

ACCESS_LEVEL_ATTR: Final = "alloq_access_level"
"""Attribute naming the guard (``viewer``/``editor``) of a decorated handler."""

CAN_EDIT: Final = UserSession.user.roles.contains(PROJECT_MANAGER_ROLE.name)
"""Frontend Var: the signed-in user may edit the planning pages."""


def has_role(user: User, role: Role) -> bool:
    """Whether ``user`` holds ``role``; the admin switch does not count."""
    return role.name in user.roles


NO_ACCESS_MSG: Final = (
    "Sie haben nicht die notwendigen Berechtigungen, um auf diese Seite zuzugreifen."
)


def no_access() -> rx.Component:
    """Page content for signed-in users without read access."""
    return mn.center(
        mn.stack(
            mn.text(NO_ACCESS_MSG, fz="15px", fw=500),
            rx.link("Zu den Angeboten", href="/offers"),
            align="center",
            gap=8,
        ),
        h="60vh",
        px=24,
    )


def viewer_only(*children: Any, fallback: rx.Component | None = None) -> rx.Component:
    """Render ``children`` for the employee role (reading)."""
    return requires_role(*children, role=EMPLOYEE_ROLE.name, fallback=fallback)


def editor_only(*children: Any, fallback: rx.Component | None = None) -> rx.Component:
    """Render ``children`` for the project manager role (edit controls)."""
    return requires_role(*children, role=PROJECT_MANAGER_ROLE.name, fallback=fallback)


def _guard[F: Callable[..., Any]](func: F, role: Role, level: str) -> F:
    """Wrap event handler ``func`` so only users holding ``role`` run it.

    Mirrors appkit's ``requires_admin``: unauthenticated callers are redirected
    to login, everyone else without the right gets a permission error.
    """

    async def _check(self: Any) -> tuple[bool, Any]:
        """``(allowed, event)``; ``event`` answers a denied call."""
        login_state = await self.get_state(LoginState)
        user = await login_state.authenticated_user
        if user is None:
            logger.debug("User not authenticated, redirecting to login.")
            return False, await login_state.redir()
        if not has_role(user, role):
            logger.warning(
                "User user_id=%s denied %s action '%s'",
                user.user_id,
                level,
                func.__name__,
            )
            return False, rx.toast.error(_NOT_AUTHORIZED_MSG, position="top-right")
        return True, None

    @wraps(func)
    async def async_gen_wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        ok, event = await _check(self)
        if not ok:
            yield event
            return
        async for item in func(self, *args, **kwargs):
            yield item

    @wraps(func)
    async def async_wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        ok, event = await _check(self)
        if not ok:
            return event
        return await func(self, *args, **kwargs)

    wrapper = async_gen_wrapper if inspect.isasyncgenfunction(func) else async_wrapper
    setattr(wrapper, ACCESS_LEVEL_ATTR, level)
    return wrapper  # type: ignore[return-value]


def requires_viewer[F: Callable[..., Any]](func: F) -> F:
    """Allow a read-only event for the employee role."""
    return _guard(func, EMPLOYEE_ROLE, "viewer")


def requires_editor[F: Callable[..., Any]](func: F) -> F:
    """Allow a reading or writing event for the project manager role."""
    return _guard(func, PROJECT_MANAGER_ROLE, "editor")


def requires_offer_editor[F: Callable[..., Any]](func: F) -> F:
    """Allow an offer event for the offer editor role."""
    return _guard(func, OFFER_EDITOR_ROLE, "offer_editor")
