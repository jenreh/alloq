"""Validate the YAML configuration profiles shipped in ``configuration/``."""

import importlib
import os
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml

from appkit_commons.configuration.configuration import Configuration, Environment
from appkit_commons.registry import ServiceRegistry

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


@pytest.fixture
def configure_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[str], Configuration[AppConfig]]:
    """Run the uncached ``configure()`` against a fresh registry."""
    monkeypatch.chdir(CONFIG_DIR.parent)
    monkeypatch.setattr(
        "appkit_commons.configuration.base.get_secret", lambda key: f"stub-{key}"
    )
    for key in list(os.environ):
        if key.startswith(("APP__", "REFLEX__", "PUBLIC_")):
            monkeypatch.delenv(key)
    module = importlib.import_module("app.configuration")
    monkeypatch.setattr(module, "service_registry", ServiceRegistry)

    def _configure(profile: str) -> Configuration[AppConfig]:
        monkeypatch.setenv("PROFILES", profile)
        return module.configure.__wrapped__()

    return _configure


def test_default_profile_requires_public_base_url(
    configure_profile: Callable[[str], Configuration[AppConfig]],
) -> None:
    with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL"):
        configure_profile("")


def test_default_profile_derives_public_urls_from_env(
    configure_profile: Callable[[str], Configuration[AppConfig]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://apps.example.com")
    monkeypatch.setenv("PUBLIC_PATH_PREFIX", "/alloq")

    config = configure_profile("")

    authentication = config.app.authentication
    assert config.app.environment == Environment.production
    assert authentication.server_url == "https://apps.example.com/alloq"
    assert authentication.server_port == 0
    assert authentication.oauth_providers
    for provider in authentication.oauth_providers:
        assert provider.redirect_url == (
            f"https://apps.example.com/alloq/oauth/{provider.provider.value}/callback"
        )
