import reflex as rx
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar

import appkit_mantine as mn
from appkit_user.user_management.components.user_profile import user_profile_view


def create_profile_page(
    sidebar: rx.Component,
    route: str = "/profile",
    title: str = "Profil",
) -> rx.Component:
    """Create the profile page with authentication.

    Args:
        sidebar: The sidebar to use in the page.

    Returns:
        The profile page component.
    """

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar("Profil", "Kontoeinstellungen und Passwort"),
    )
    def _profile_page() -> rx.Component:
        """The profile page.

        Returns:
            The UI for the profile page.
        """
        return mn.box(user_profile_view(padding="0"), max_width="800px", w="100%")

    return _profile_page
