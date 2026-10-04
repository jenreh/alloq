import logging
from functools import lru_cache

from appkit_commons.configuration.configuration import (
    ApplicationConfig,
    Configuration,
    Environment,
)
from appkit_commons.registry import service_registry
from appkit_user.configuration import AuthenticationConfiguration

from app.public_url import PUBLIC_BASE_URL_ENV, PublicUrl, apply_public_url

logger = logging.getLogger(__name__)


class AppConfig(ApplicationConfig):
    authentication: AuthenticationConfiguration
    # Peer addresses allowed to set X-Forwarded-Proto. None trusts every peer,
    # so set it wherever the backend port is reachable without the proxy.
    trusted_proxies: set[str] | None = None


@lru_cache(maxsize=1)
def configure() -> Configuration[AppConfig]:
    logger.debug("--- Configuring application settings ---")
    config = service_registry().configure(
        AppConfig,
        env_file=".env",
    )
    public_url = PublicUrl.from_env()
    if public_url is not None:
        apply_public_url(public_url, config.reflex, config.app.authentication)
    elif config.app.environment == Environment.production:
        msg = f"{PUBLIC_BASE_URL_ENV} must be set in production"
        raise RuntimeError(msg)
    return config
