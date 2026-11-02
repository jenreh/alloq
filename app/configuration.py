import logging
from functools import lru_cache
from typing import Any

from alloq_offer.workshop.configuration import WorkshopConfig
from pydantic import field_validator

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
    # Background worker and Azure OpenAI access of the offer workshop.
    offer_workshop: WorkshopConfig = WorkshopConfig()

    @field_validator("trusted_proxies", mode="before")
    @classmethod
    def _split_trusted_proxies(cls, value: Any) -> Any:
        """A secret resolves to one string: comma-separated addresses."""
        if isinstance(value, str):
            return {host.strip() for host in value.split(",") if host.strip()}
        return value


def check_production_security(app: AppConfig) -> None:
    """Refuse insecure session settings in production; warn about open proxies."""
    if app.environment != Environment.production:
        return
    if not app.authentication.session_cookie_secure:
        msg = "authentication.session_cookie_secure must be true in production"
        raise RuntimeError(msg)
    if app.trusted_proxies is None:
        logger.warning(
            "trusted_proxies is not set: X-Forwarded-Proto is trusted from every peer"
        )


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
    check_production_security(config.app)
    return config
