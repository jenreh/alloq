"""Small helpers shared by the workshop states."""

import reflex as rx

from alloq_offer.workshop.states.workshop_state import WorkshopState
from appkit_user.authentication.states import LoginState


def browser_int(value: object) -> int | None:
    """A number sent by the browser; anything else is ``None``."""
    try:
        return int(value)
    except TypeError, ValueError:
        return None


async def current_user_name(state: rx.State) -> str:
    login = await state.get_state(LoginState)
    user = await login.authenticated_user
    return user.name if user else ""


async def open_offer_id(state: rx.State) -> int:
    """The offer the workshop page shows; 0 before it is loaded."""
    return (await state.get_state(WorkshopState)).offer_id
