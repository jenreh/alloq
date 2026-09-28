import logging

import reflex as rx

from appkit_commons.configuration.configuration import ReflexConfig
from appkit_commons.configuration.logging import init_logging
from appkit_commons.database.configuration import DatabaseConfig
from appkit_commons.registry import service_registry

from app import configuration

init_logging(configuration)
logger = logging.getLogger(__name__)


def _lookup[T](config_type: type[T]) -> T | None:
    try:
        return service_registry().get(config_type)
    except KeyError:
        return None


def _require_database() -> DatabaseConfig:
    database = _lookup(DatabaseConfig)
    if database is None:
        msg = "No app.database configuration found; check the active PROFILES."
        raise RuntimeError(msg)
    return database


def _url_settings(reflex: ReflexConfig | None) -> dict[str, str]:
    """Pass deploy_url/api_url from YAML; unset values keep Reflex's defaults."""
    if reflex is None:
        return {}
    urls = {"deploy_url": reflex.deploy_url, "api_url": reflex.api_url}
    return {key: value for key, value in urls.items() if value}


database = _require_database()
reflex = _lookup(ReflexConfig)

config = rx.Config(
    app_name="app",
    frontend_port=reflex.frontend_port if reflex else 8080,
    backend_port=reflex.backend_port if reflex else 3030,
    gunicorn_workers=reflex.workers if reflex else 1,
    db_url=database.url,
    async_db_url=database.url,
    **_url_settings(reflex),
    telemetry_enabled=False,
    show_built_with_reflex=False,
    plugins=[
        # rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(),
    ],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
