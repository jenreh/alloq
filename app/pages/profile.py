from collections.abc import Callable

import reflex as rx
from alloq_commons.components import page_header

import appkit_mantine as mn
from appkit_user.authentication.templates import (
    authenticated,
)
from appkit_user.user_management.components.user_profile import user_profile_view

ROLES = []


def create_profile_page(
    navbar: rx.Component,
    route: str = "/profile",
    title: str = "Profil",
    **kwargs,
) -> Callable:
    """Create the profile page with authentication.

    Args:
        navbar: The navigation bar to use in the page.

    Returns:
        The profile page component.
    """

    @authenticated(
        route=route,
        title=title,
        navbar=navbar,
        with_header=False,
    )
    def _profile_page() -> rx.Component:
        """The profile page.

        Returns:
            The UI for the profile page.
        """
        return mn.stack(
            page_header(
                title="Kontoeinstellungen",
                description="Verwalten Sie Ihre Kontoeinstellungen und das Passwort.",
                pl="2rem",
            ),
            user_profile_view(**kwargs),
            gap="0",
        )

    return _profile_page
