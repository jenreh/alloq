import logging
from typing import TypedDict

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


class _UrlSettings(TypedDict, total=False):
    deploy_url: str
    api_url: str


def _url_settings(reflex: ReflexConfig | None) -> _UrlSettings:
    """Pass deploy_url/api_url from YAML; unset values keep Reflex's defaults."""
    settings: _UrlSettings = {}
    if reflex is None:
        return settings
    if reflex.deploy_url:
        settings["deploy_url"] = reflex.deploy_url
    if reflex.api_url:
        settings["api_url"] = reflex.api_url
    return settings


class _PortSettings(TypedDict, total=False):
    frontend_port: int
    backend_port: int


def _port_settings(reflex: ReflexConfig | None) -> _PortSettings:
    """Pass only ports the YAML sets explicitly; others keep Reflex's defaults.

    A configured frontend port makes `reflex run --backend-only` exit, so the
    production profile leaves it to REFLEX_FRONTEND_PORT or --frontend-port.
    """
    settings: _PortSettings = {}
    if reflex is None:
        return settings
    if "frontend_port" in reflex.model_fields_set:
        settings["frontend_port"] = reflex.frontend_port
    if "backend_port" in reflex.model_fields_set:
        settings["backend_port"] = reflex.backend_port
    return settings


database = _require_database()
reflex = _lookup(ReflexConfig)

config = rx.Config(
    app_name="app",
    **_port_settings(reflex),
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
