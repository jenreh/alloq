"""Public URL derivation for serving the app under a path prefix."""

import pytest

from appkit_commons.configuration.configuration import ReflexConfig
from appkit_user.configuration import (
    AuthenticationConfiguration,
    AzureOAuthConfig,
    GithubOAuthConfig,
)

from app.public_url import (
    DEFAULT_API_URL,
    DEFAULT_DEPLOY_URL,
    PUBLIC_BASE_URL_ENV,
    PUBLIC_PATH_PREFIX_ENV,
    PublicUrl,
    PublicUrlError,
    apply_public_url,
    reflex_server_urls,
)

BASE = "https://apps.example.com"


def _authentication() -> AuthenticationConfiguration:
    return AuthenticationConfiguration(
        server_url="http://localhost",
        server_port=8080,
        oauth_providers=[
            GithubOAuthConfig(
                client_id="gh",
                client_secret="gh-secret",  # noqa: S106
                redirect_url="http://localhost:8080/oauth/github/callback",
            ),
            AzureOAuthConfig(client_id="az", client_secret="az-secret"),  # noqa: S106
        ],
    )


class TestPublicUrlCreate:
    @pytest.mark.parametrize(
        ("prefix", "expected"),
        [
            ("/alloq", "/alloq"),
            ("alloq", "/alloq"),
            ("/alloq/", "/alloq"),
            ("/a/b", "/a/b"),
            ("", ""),
            ("/", ""),
            ("  ", ""),
        ],
    )
    def test_normalizes_prefix(self, prefix: str, expected: str) -> None:
        assert PublicUrl.create(BASE, prefix).path_prefix == expected

    @pytest.mark.parametrize("base", [BASE, f"{BASE}/", f"  {BASE}  "])
    def test_normalizes_base_url(self, base: str) -> None:
        assert PublicUrl.create(base).base_url == BASE

    def test_keeps_port(self) -> None:
        assert PublicUrl.create("http://localhost:8080").base_url == (
            "http://localhost:8080"
        )

    @pytest.mark.parametrize(
        "base",
        [
            "apps.example.com",
            "ftp://apps.example.com",
            "https://",
            f"{BASE}/alloq",
            f"{BASE}?x=1",
            f"{BASE}#top",
        ],
    )
    def test_rejects_invalid_base_url(self, base: str) -> None:
        with pytest.raises(PublicUrlError):
            PublicUrl.create(base)

    @pytest.mark.parametrize("prefix", ["/al loq", "/alloq?x", "/a//b", "/alloq#x"])
    def test_rejects_invalid_prefix(self, prefix: str) -> None:
        with pytest.raises(PublicUrlError):
            PublicUrl.create(BASE, prefix)


class TestPublicUrlUrls:
    def test_app_url_includes_prefix(self) -> None:
        assert PublicUrl.create(BASE, "/alloq").app_url == f"{BASE}/alloq"

    def test_app_url_without_prefix(self) -> None:
        assert PublicUrl.create(BASE).app_url == BASE

    @pytest.mark.parametrize("path", ["/login", "login"])
    def test_url_joins_path(self, path: str) -> None:
        assert PublicUrl.create(BASE, "/alloq").url(path) == f"{BASE}/alloq/login"


class TestPublicUrlFromEnv:
    def test_reads_base_url_and_prefix(self) -> None:
        env = {PUBLIC_BASE_URL_ENV: BASE, PUBLIC_PATH_PREFIX_ENV: "/alloq"}
        assert PublicUrl.from_env(env) == PublicUrl(BASE, "/alloq")

    def test_prefix_is_optional(self) -> None:
        assert PublicUrl.from_env({PUBLIC_BASE_URL_ENV: BASE}) == PublicUrl(BASE)

    def test_none_without_base_url(self) -> None:
        assert PublicUrl.from_env({}) is None

    def test_prefix_without_base_url_is_ignored(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        assert PublicUrl.from_env({PUBLIC_PATH_PREFIX_ENV: "/alloq"}) is None
        assert PUBLIC_PATH_PREFIX_ENV in caplog.text

    def test_defaults_to_process_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(PUBLIC_BASE_URL_ENV, BASE)
        monkeypatch.setenv(PUBLIC_PATH_PREFIX_ENV, "alloq/")
        assert PublicUrl.from_env() == PublicUrl(BASE, "/alloq")


class TestApplyPublicUrl:
    def test_derives_authentication_urls(self) -> None:
        authentication = _authentication()

        apply_public_url(PublicUrl.create(BASE, "/alloq"), None, authentication)

        assert authentication.server_url == f"{BASE}/alloq"
        assert authentication.server_port == 0
        assert [p.redirect_url for p in authentication.oauth_providers] == [
            f"{BASE}/alloq/oauth/github/callback",
            f"{BASE}/alloq/oauth/azure/callback",
        ]

    def test_reflex_urls_include_prefix_for_appkit_api_links(self) -> None:
        reflex = ReflexConfig(api_url=DEFAULT_API_URL, deploy_url=DEFAULT_DEPLOY_URL)

        apply_public_url(PublicUrl.create(BASE, "/alloq"), reflex, _authentication())

        assert reflex.api_url == f"{BASE}/alloq"
        assert reflex.deploy_url == f"{BASE}/alloq"

    @pytest.mark.parametrize(
        ("base", "port"),
        [(BASE, 443), ("http://apps.example.com", 80), ("http://localhost:8080", 80)],
    )
    def test_frontend_port_is_scheme_default(self, base: str, port: int) -> None:
        # appkit appends frontend_port to deploy_url (MCP OAuth callback) unless
        # it is 80/443; an explicit port already lives in base_url.
        reflex = ReflexConfig(frontend_port=8080)

        apply_public_url(PublicUrl.create(base, "/alloq"), reflex, _authentication())

        assert reflex.frontend_port == port


class TestReflexServerUrls:
    def test_public_url_gives_bare_origin(self) -> None:
        reflex = ReflexConfig(api_url=f"{BASE}/alloq", deploy_url=f"{BASE}/alloq")
        public_url = PublicUrl.create(BASE, "/alloq")

        assert reflex_server_urls(public_url, reflex) == (BASE, BASE)

    def test_configured_urls_without_public_url(self) -> None:
        reflex = ReflexConfig(
            api_url="http://localhost:3030", deploy_url="http://localhost:8080"
        )
        assert reflex_server_urls(None, reflex) == (
            "http://localhost:3030",
            "http://localhost:8080",
        )

    def test_defaults_without_any_config(self) -> None:
        assert reflex_server_urls(None, None) == (DEFAULT_API_URL, DEFAULT_DEPLOY_URL)

    def test_defaults_for_missing_values(self) -> None:
        reflex = ReflexConfig(api_url=None, deploy_url=None)
        assert reflex_server_urls(None, reflex) == (DEFAULT_API_URL, DEFAULT_DEPLOY_URL)
