import logging

import reflex as rx
from alloq_dashboard.pages import create_dashboard_page
from alloq_project.pages import create_planning_page, create_projects_overview_page
from alloq_team.pages import create_team_overview_page
from reflex.assets import asset
from starlette.types import ASGIApp

import appkit_mantine.base
from appkit_commons.middleware import ForceHTTPSMiddleware
from appkit_user.authentication.pages import (  # noqa: F401
    azure_oauth_callback_page,
    github_oauth_callback_page,
)
from appkit_user.user_management.pages import (
    create_login_page,
    create_password_reset_confirm_page,
    create_password_reset_request_page,
)

from app.components.navbar_collapsible import app_navbar_collapsible
from app.pages.holidays import create_holidays_page
from app.pages.profile import create_profile_page
from app.pages.roles import create_roles_page
from app.pages.users import create_users_page
from app.styles import base_style, base_stylesheets

ALLOQ_THEME = {
    "primaryColor": "alloqTeal",
    "primaryShade": {"light": 6, "dark": 7},
    "colors": {
        "alloqWarm": [
            "#fffef8",
            "#fbf8ed",
            "#f7efd1",
            "#f8eaa8",
            "#f6d94d",
            "#f1ca45",
            "#d99f18",
            "#a97811",
            "#6f4f0f",
            "#3e2d0b",
        ],
        "alloqTeal": [
            "#eef8f8",
            "#d9eeee",
            "#b9dddd",
            "#95c7c8",
            "#6f9fa5",
            "#5b858b",
            "#486d73",
            "#3c5a5f",
            "#32494e",
            "#293c40",
        ],
    },
}

ALLOQ_MANTINE_PROVIDER_PATH = asset(
    path="mantine_provider.js",
    shared=True,
).importable_path


class _CustomMemoizedMantineProvider(appkit_mantine.base.MemoizedMantineProvider):
    library = ALLOQ_MANTINE_PROVIDER_PATH
    theme: rx.Var[dict]


appkit_mantine.base.MantineComponentBase._get_app_wrap_components = staticmethod(  # noqa: SLF001
    lambda: {
        (44, "MantineProvider"): _CustomMemoizedMantineProvider.create(
            theme=ALLOQ_THEME  # type: ignore[call-arg]
        ),
    }
)

logging.basicConfig(level=logging.DEBUG)
create_login_page()
create_profile_page(
    app_navbar_collapsible(),
    class_name="w-full gap-6 max-w-[800px]",
    padding="2rem",
)
create_password_reset_request_page()
create_password_reset_confirm_page()
create_users_page(app_navbar_collapsible())
create_roles_page(app_navbar_collapsible())
create_holidays_page(app_navbar_collapsible())
create_team_overview_page(app_navbar_collapsible())
create_projects_overview_page(app_navbar_collapsible())
create_planning_page(app_navbar_collapsible())
create_dashboard_page(app_navbar_collapsible())


# Middleware transformer for HTTPS redirect
def add_https_middleware(asgi_app: ASGIApp) -> ASGIApp:
    """Wrap the ASGI app with HTTPS redirect middleware."""
    return ForceHTTPSMiddleware(asgi_app)


app = rx.App(
    stylesheets=base_stylesheets,
    style=base_style,
    api_transformer=[add_https_middleware],
)
