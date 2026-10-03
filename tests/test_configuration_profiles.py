"""Validate the YAML configuration profiles shipped in ``configuration/``."""

import os
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml
from pydantic import ValidationError

from appkit_commons.configuration.configuration import Configuration, Environment

from app.configuration import AppConfig

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configuration"
PROFILE_FILES = sorted(CONFIG_DIR.glob("config*.yaml"))


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_profiles_found() -> None:
    assert any(p.name == "config.yaml" for p in PROFILE_FILES)


@pytest.mark.parametrize("path", PROFILE_FILES, ids=lambda p: p.name)
def test_environment_is_valid_enum_value(path: Path) -> None:
    environment = _load(path).get("app", {}).get("environment")
    if environment is None:
        pytest.skip("profile does not set app.environment")

    assert environment in {e.value for e in Environment}


@pytest.mark.parametrize("path", PROFILE_FILES, ids=lambda p: p.name)
def test_logging_file_exists(path: Path) -> None:
    logging_file = _load(path).get("app", {}).get("logging")
    if logging_file is None:
        pytest.skip("profile does not set app.logging")

    assert (CONFIG_DIR / logging_file).is_file()


def test_prod_logging_has_no_ansi_colors() -> None:
    config = _load(CONFIG_DIR / "logging.prod.yaml")

    for handler in config["handlers"].values():
        formatter = config["formatters"][handler["formatter"]]
        assert "colorlog" not in str(formatter.get("()", ""))


# ── Full load through the real settings pipeline ─────────────────────────────


@pytest.fixture
def load_profile(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], AppConfig]:
    """Load ``Configuration[AppConfig]`` for a profile with stubbed secrets."""
    monkeypatch.chdir(CONFIG_DIR.parent)
    monkeypatch.setattr(
        "appkit_commons.configuration.base.get_secret", lambda key: f"stub-{key}"
    )
    for key in list(os.environ):
        if key.startswith(("APP__", "REFLEX__")):
            monkeypatch.delenv(key)

    def _load(profile: str) -> AppConfig:
        monkeypatch.setenv("PROFILES", profile)
        return Configuration[AppConfig](_env_file=None).app

    return _load


@pytest.mark.parametrize("profile", ["local", "docker_test"])
def test_profile_loads(load_profile: Callable[[str], AppConfig], profile: str) -> None:
    app_config = load_profile(profile)

    assert app_config.environment is not None
    server_url = urlsplit(app_config.authentication.server_url)
    assert server_url.scheme in {"http", "https"}
    # appkit_user appends ":<server_port>" itself; a port here doubles it.
    assert server_url.port is None


@pytest.mark.parametrize("field", ["server_url", "server_port"])
def test_default_profile_requires_public_address_from_env(
    load_profile: Callable[[str], AppConfig], field: str
) -> None:
    with pytest.raises(ValidationError, match=field):
        load_profile("")


def test_default_profile_has_no_localhost_urls(
    load_profile: Callable[[str], AppConfig], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP__AUTHENTICATION__SERVER_URL", "https://alloq.example.com")
    monkeypatch.setenv("APP__AUTHENTICATION__SERVER_PORT", "443")

    app_config = load_profile("")

    assert app_config.environment == Environment.production
    assert app_config.authentication.server_url == "https://alloq.example.com"
    for provider in app_config.authentication.oauth_providers:
        # Derived from server_url by the OAuth service when unset.
        assert provider.redirect_url is None


def test_default_profile_serves_below_base_path_from_env(
    load_profile: Callable[[str], AppConfig], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP__AUTHENTICATION__SERVER_URL", "https://apps.example.com")
    monkeypatch.setenv("APP__AUTHENTICATION__SERVER_PORT", "443")
    monkeypatch.setenv("APP__BASE_PATH", "/alloq")

    app_config = load_profile("")

    assert app_config.base_path == "/alloq"
    assert app_config.authentication.oauth_providers
    for provider in app_config.authentication.oauth_providers:
        assert provider.redirect_url == (
            f"https://apps.example.com:443/alloq/oauth/{provider.provider}/callback"
        )


@pytest.mark.parametrize(
    ("profile", "frontend_port"),
    [("", None), ("local", 8080), ("devcontainer", 8080), ("docker_test", 8080)],
)
def test_frontend_port_per_profile(
    load_profile: Callable[[str], AppConfig],
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    frontend_port: int | None,
) -> None:
    """Production must not pin a frontend port: it runs `--backend-only`."""
    monkeypatch.setenv("APP__AUTHENTICATION__SERVER_URL", "https://alloq.example.com")
    monkeypatch.setenv("APP__AUTHENTICATION__SERVER_PORT", "443")
    load_profile(profile)  # applies the env/secret stubs and PROFILES

    reflex = Configuration[AppConfig](_env_file=None).reflex

    assert reflex is not None
    configured = (
        reflex.frontend_port if "frontend_port" in reflex.model_fields_set else None
    )
    assert configured == frontend_port
