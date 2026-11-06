import reflex as rx
from alloq_commons import theme
from alloq_commons.components.shell import SIDEBAR_SCRIPT
from alloq_dashboard.pages import create_dashboard_page
from alloq_offer.admin.pages import create_offer_admin_page
from alloq_offer.pages import create_offers_page
from alloq_offer.workshop import worker as _workshop_worker  # noqa: F401 - register jobs
from alloq_offer.workshop.image_api import router as offer_image_router
from alloq_offer.workshop.pages import create_offer_workshop_page
from alloq_project.pages import create_planning_page, create_projects_overview_page
from alloq_team.pages import create_team_overview_page
from fastapi import FastAPI
from starlette.types import ASGIApp

import appkit_mantine as am
from appkit_commons.middleware import ForceHTTPSMiddleware, SecurityHeadersMiddleware
from appkit_user.authentication import add_session_guard
from appkit_user.authentication.pages import (  # noqa: F401
    azure_oauth_callback_page,
    github_oauth_callback_page,
)
from appkit_user.user_management.pages import (
    create_password_reset_confirm_page,
    create_password_reset_request_page,
)

from app.backup_api import router as backup_router
from app.components.sidebar import sidebar
from app.configuration import configure
from app.database_backup.maintenance import install_maintenance_guard
from app.database_backup.runtime import (
    BackupApp,
    BackupSessionFilter,
    backup_aware_worker,
)
from app.database_backup.storage import backup_cleanup_worker
from app.pages.backups import create_backups_page
from app.pages.daily_rates import create_daily_rates_page
from app.pages.departments import create_departments_page
from app.pages.holidays import create_holidays_page
from app.pages.industries import create_industries_page
from app.pages.login import create_login_page
from app.pages.profile import create_profile_page
from app.pages.roles import create_roles_page
from app.pages.users import create_users_page
from app.styles import base_style, base_stylesheets

am.set_app_theme(theme.MANTINE_THEME)
install_maintenance_guard()


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
create_backups_page(sidebar())
create_roles_page(sidebar())
create_daily_rates_page(sidebar())
create_departments_page(sidebar())
create_holidays_page(sidebar())
create_industries_page(sidebar())
create_offer_admin_page(sidebar())
create_team_overview_page(sidebar())
create_projects_overview_page(sidebar())
create_offers_page(sidebar())
create_offer_workshop_page(sidebar())
create_planning_page(sidebar(), route="/")
create_planning_page(sidebar())
create_dashboard_page(sidebar(), route="/dashboard")


def add_https_middleware(asgi_app: ASGIApp) -> ASGIApp:
    """Honor X-Forwarded-Proto from trusted proxies (sets the scheme, no redirect)."""
    return ForceHTTPSMiddleware(asgi_app, trusted_hosts=configure().app.trusted_proxies)


def add_security_headers(asgi_app: ASGIApp) -> ASGIApp:
    """Add the security response headers (inside the HTTPS scheme fix)."""
    return SecurityHeadersMiddleware(asgi_app)


def create_rest_api() -> FastAPI:
    """REST routes; Reflex mounts its own backend below them.

    Reflex applies the transformers in order, so the session guard and the
    HTTPS middleware wrap these routes too. No docs: the API is internal.
    """
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    api.include_router(offer_image_router, prefix=rx.config.get_config().backend_path)
    api.include_router(backup_router, prefix=rx.config.get_config().backend_path)
    return api


app = BackupApp(
    head_components=[
        rx.el.link(rel="icon", href=rx.asset("favicon.ico"), type="image/x-icon"),
        rx.el.style(theme.GLOBAL_CSS),
        rx.script(SIDEBAR_SCRIPT),
    ],
    stylesheets=base_stylesheets,
    style=base_style,
    toaster=rx.toast.provider(close_button=True),
    api_transformer=[
        create_rest_api(),
        add_session_guard,
        add_security_headers,
        add_https_middleware,
    ],
)

app.add_middleware(BackupSessionFilter())
app.register_lifespan_task(backup_aware_worker)
app.register_lifespan_task(backup_cleanup_worker)
