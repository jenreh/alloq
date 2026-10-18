"""Access levels of the alloq roles next to appkit's admin rights.

Admins may do everything. Project managers may read and edit every planning
page; the administration pages stay admin-only (``@requires_admin``). Users
with the employee role may only read the projects and planning pages.
"""

import inspect
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, Final

import reflex as rx

import appkit_mantine as mn
from alloq_commons.roles import EMPLOYEE_ROLE, PROJECT_MANAGER_ROLE
from appkit_user.authentication.backend.models import User
from appkit_user.authentication.states import LoginState, UserSession

logger = logging.getLogger(__name__)

_NOT_AUTHORIZED_MSG: Final = "Sie haben keine Berechtigung für diese Aktion."

ACCESS_LEVEL_ATTR: Final = "alloq_access_level"
"""Attribute naming the guard (``viewer``/``editor``) of a decorated handler."""

IS_ADMIN: Final = UserSession.user.is_admin
"""Frontend Var: the signed-in user is an admin."""
CAN_EDIT: Final = IS_ADMIN | UserSession.user.roles.contains(PROJECT_MANAGER_ROLE.name)
"""Frontend Var: the signed-in user may read and edit the planning pages."""
CAN_VIEW: Final = CAN_EDIT | UserSession.user.roles.contains(EMPLOYEE_ROLE.name)
"""Frontend Var: the signed-in user may read projects and planning."""


def can_edit(user: User) -> bool:
    """Whether ``user`` may read and edit the planning pages."""
    return user.is_admin or PROJECT_MANAGER_ROLE.name in user.roles


def can_view(user: User) -> bool:
    """Whether ``user`` may read the projects and planning pages."""
    return can_edit(user) or EMPLOYEE_ROLE.name in user.roles


NO_ACCESS_MSG: Final = (
    "Sie haben nicht die notwendigen Berechtigungen, um auf diese Seite zuzugreifen."
)


def no_access() -> rx.Component:
    """Page content for signed-in users without read access."""
    return mn.center(mn.text(NO_ACCESS_MSG, fz="15px", fw=500), h="60vh", px=24)


def viewer_only(*children: Any, fallback: rx.Component | None = None) -> rx.Component:
    """Render ``children`` for admins, project managers and employees."""
    return rx.cond(CAN_VIEW, rx.fragment(*children), fallback)


def editor_only(*children: Any, fallback: rx.Component | None = None) -> rx.Component:
    """Render ``children`` for admins and project managers (edit controls)."""
    return rx.cond(CAN_EDIT, rx.fragment(*children), fallback)


def admin_only(*children: Any, fallback: rx.Component | None = None) -> rx.Component:
    """Render ``children`` for admins only (administration)."""
    return rx.cond(IS_ADMIN, rx.fragment(*children), fallback)


def _guard[F: Callable[..., Any]](
    func: F, allowed: Callable[[User], bool], level: str
) -> F:
    """Wrap event handler ``func`` so only users passing ``allowed`` run it.

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
        if not allowed(user):
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
    """Allow a read-only event for admins, project managers and employees."""
    return _guard(func, can_view, "viewer")


def requires_editor[F: Callable[..., Any]](func: F) -> F:
    """Allow a reading or writing event for admins and project managers."""
    return _guard(func, can_edit, "editor")
