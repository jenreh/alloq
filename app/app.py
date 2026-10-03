import reflex as rx
from alloq_dashboard.pages import create_dashboard_page
from alloq_project.pages import create_planning_page, create_projects_overview_page
from alloq_team.pages import create_team_overview_page
from starlette.types import ASGIApp

import appkit_mantine as am
from appkit_commons.middleware import ForceHTTPSMiddleware
from appkit_user.authentication import add_session_guard, install_session_filter
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
from app.configuration import configure
from app.pages.holidays import create_holidays_page
from app.pages.profile import create_profile_page
from app.pages.roles import create_roles_page
from app.pages.users import create_users_page
from app.styles import base_style, base_stylesheets

ALLOQ_THEME = am.create_theme(
    primary_color="alloqTeal",
    primary_shade={"light": 6, "dark": 7},
    colors={
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
)

am.set_app_theme(ALLOQ_THEME)


def auth_page_logos() -> dict[str, str]:
    """Logos for appkit's auth pages, honoring Reflex's frontend_path.

    appkit_user defaults to raw "/img/..." paths, which miss the prefix when
    the app is served below the site root.
    """
    return {
        "logo": rx.asset("img/appkit_logo.svg"),
        "logo_dark": rx.asset("img/appkit_logo_dark.svg"),
    }


create_login_page(**auth_page_logos())
create_profile_page(app_navbar_collapsible())
create_password_reset_request_page(**auth_page_logos())
create_password_reset_confirm_page(**auth_page_logos())
create_users_page(app_navbar_collapsible())
create_roles_page(app_navbar_collapsible())
create_holidays_page(app_navbar_collapsible())
create_team_overview_page(app_navbar_collapsible())
create_projects_overview_page(app_navbar_collapsible())
create_planning_page(app_navbar_collapsible())
create_dashboard_page(app_navbar_collapsible())


def add_https_middleware(asgi_app: ASGIApp) -> ASGIApp:
    """Honor X-Forwarded-Proto from trusted proxies (sets the scheme, no redirect)."""
    return ForceHTTPSMiddleware(asgi_app, trusted_hosts=configure().app.trusted_proxies)


app = rx.App(
    stylesheets=base_stylesheets,
    style=base_style,
    api_transformer=[add_session_guard, add_https_middleware],
)

install_session_filter(app)
