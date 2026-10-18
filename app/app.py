import reflex as rx
from alloq_commons import theme
from alloq_commons.components.shell import SIDEBAR_SCRIPT
from alloq_commons.desktop import is_desktop
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
    create_password_reset_confirm_page,
    create_password_reset_request_page,
)

from app.components.sidebar import sidebar
from app.configuration import configure
from app.desktop.entra import EntraSignIn, install_db_auth
from app.desktop.login_state import get_sign_in
from app.pages.departments import create_departments_page
from app.pages.holidays import create_holidays_page
from app.pages.login import create_login_page
from app.pages.profile import create_profile_page
from app.pages.roles import create_roles_page
from app.pages.users import create_users_page
from app.styles import base_style, base_stylesheets

am.set_app_theme(theme.MANTINE_THEME)

if is_desktop() and isinstance(sign_in := get_sign_in(), EntraSignIn):
    # Every database connection signs in with the user's Entra token.
    install_db_auth(sign_in)


def auth_page_logos() -> dict[str, str]:
    """Logos for appkit's auth pages, honoring Reflex's frontend_path.

    appkit_user defaults to raw "/img/..." paths, which miss the prefix when
    the app is served below the site root.
    """
    return {
        "logo": rx.asset("img/appkit_logo.svg"),
        "logo_dark": rx.asset("img/appkit_logo_dark.svg"),
    }


create_login_page()
create_profile_page(sidebar())
create_password_reset_request_page(**auth_page_logos())
create_password_reset_confirm_page(**auth_page_logos())
create_users_page(sidebar())
create_roles_page(sidebar())
create_departments_page(sidebar())
create_holidays_page(sidebar())
create_team_overview_page(sidebar())
create_projects_overview_page(sidebar())
create_planning_page(sidebar(), route="/")
create_planning_page(sidebar())
create_dashboard_page(sidebar(), route="/dashboard")


def add_https_middleware(asgi_app: ASGIApp) -> ASGIApp:
    """Honor X-Forwarded-Proto from trusted proxies (sets the scheme, no redirect)."""
    return ForceHTTPSMiddleware(asgi_app, trusted_hosts=configure().app.trusted_proxies)


app = rx.App(
    head_components=[
        rx.el.link(rel="icon", href=rx.asset("favicon.ico"), type="image/x-icon"),
        rx.el.style(theme.GLOBAL_CSS),
        *(rx.script(script) for script in (*theme.HEAD_SCRIPTS, SIDEBAR_SCRIPT)),
    ],
    stylesheets=base_stylesheets,
    style=base_style,
    api_transformer=[add_session_guard, add_https_middleware],
)

install_session_filter(app)
