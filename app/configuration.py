import logging
from functools import lru_cache
from typing import Self

from pydantic import field_validator, model_validator

from appkit_commons.configuration.configuration import (
    ApplicationConfig,
    Configuration,
)
from appkit_commons.registry import service_registry
from appkit_user.configuration import AuthenticationConfiguration

logger = logging.getLogger(__name__)


class AppConfig(ApplicationConfig):
    authentication: AuthenticationConfiguration
    # Peer addresses allowed to set X-Forwarded-Proto. None trusts every peer,
    # so set it wherever the backend port is reachable without the proxy.
    trusted_proxies: set[str] | None = None
    # Public URL path the app is served under when a reverse proxy mounts it
    # below the site root (e.g. "/alloq" via APP__BASE_PATH); "" serves at "/".
    base_path: str = ""

    @field_validator("base_path")
    @classmethod
    def _normalize_base_path(cls, value: str) -> str:
        segments = value.strip().strip("/")
        return f"/{segments}" if segments else ""

    @model_validator(mode="after")
    def _prefix_oauth_redirect_urls(self) -> Self:
        """Put base_path into derived OAuth callbacks; appkit_user omits it."""
        if not self.base_path:
            return self

        auth = self.authentication
        origin = f"{auth.server_url}:{auth.server_port}{self.base_path}"
        for provider in auth.oauth_providers:
            if provider.redirect_url is None:
                provider.redirect_url = (
                    f"{origin}/oauth/{provider.provider.value}/callback"
                )
                logger.debug("OAuth redirect URL derived: %s", provider.redirect_url)
        return self


@lru_cache(maxsize=1)
def configure() -> Configuration[AppConfig]:
    logger.debug("--- Configuring application settings ---")
    return service_registry().configure(
        AppConfig,
        env_file=".env",
    )
