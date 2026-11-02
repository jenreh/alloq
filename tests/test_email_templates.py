"""The password reset emails that appkit renders from assets/email-templates."""

import html
import re
from pathlib import Path
from typing import Final
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from alloq_commons import theme

from appkit_user.authentication.backend.services import email_service
from appkit_user.authentication.backend.services.email_service import (
    MockEmailProvider,
)
from appkit_user.authentication.backend.types import PasswordResetType
from appkit_user.configuration import (
    AuthenticationConfiguration,
    MockEmailConfig,
    PasswordResetConfig,
)

ROOT: Final = Path(__file__).parent.parent
TEMPLATES: Final = ROOT / "assets" / "email-templates"
LOGO: Final = "img/alloq_icon.png"
RESET_URL: Final = "https://apps.example.com/alloq/password-reset/confirm?token=a&b=c"
RESET_TYPES: Final = (PasswordResetType.USER_INITIATED, PasswordResetType.ADMIN_FORCED)
THEME_COLORS: Final = " ".join(
    [*theme.BLUE, *theme.TOKENS.values(), *theme.DARK_TOKENS.values()]
).casefold()


def _base_config() -> dict:
    return yaml.safe_load((ROOT / "configuration" / "config.yaml").read_text())


async def _render(reset_type: PasswordResetType, user_name: str = "Erika") -> str:
    config = AuthenticationConfiguration(
        server_url="https://apps.example.com",
        server_port=0,
        password_reset=PasswordResetConfig(templates_dir=TEMPLATES),
    )
    registry = MagicMock()
    registry.get.return_value = config
    provider = MockEmailProvider(MockEmailConfig.model_validate({"provider": "mock"}))
    send = AsyncMock(return_value=True)

    with (
        patch.object(email_service, "service_registry", return_value=registry),
        patch.object(provider, "send_email", send),
    ):
        sent = await provider.send_password_reset_email(
            "erika@example.com", RESET_URL, user_name, reset_type
        )

    assert sent is True
    return send.await_args.args[2]


class TestTemplateConfiguration:
    def test_config_points_at_the_alloq_templates(self) -> None:
        reset = _base_config()["app"]["authentication"]["password_reset"]

        assert (ROOT / reset["templates_dir"]).resolve() == TEMPLATES

    def test_logo_is_a_png_that_exists(self) -> None:
        # Gmail and Outlook do not show SVG images.
        assert (ROOT / "assets" / LOGO).is_file()


@pytest.mark.parametrize("reset_type", RESET_TYPES)
class TestRenderedEmail:
    async def test_links_to_the_reset_page(self, reset_type: PasswordResetType) -> None:
        body = await _render(reset_type)

        assert f'href="{html.escape(RESET_URL)}"' in body

    async def test_shows_the_link_as_text_for_blocked_buttons(
        self, reset_type: PasswordResetType
    ) -> None:
        body = await _render(reset_type)

        assert f">{html.escape(RESET_URL)}</a>" in body

    async def test_uses_the_alloq_logo_from_the_public_address(
        self, reset_type: PasswordResetType
    ) -> None:
        body = await _render(reset_type)

        assert f'/{LOGO}"' in body
        assert 'src="https://apps.example.com' in body

    async def test_has_no_appkit_branding(self, reset_type: PasswordResetType) -> None:
        body = await _render(reset_type)

        assert "appkit" not in body.casefold()
        assert "ASSETS" not in body

    async def test_states_the_configured_link_lifetime(
        self, reset_type: PasswordResetType
    ) -> None:
        reset = _base_config()["app"]["authentication"]["password_reset"]

        body = await _render(reset_type)

        assert f"{reset['token_expiry_minutes']} Minuten" in body

    async def test_greets_by_name(self, reset_type: PasswordResetType) -> None:
        assert "Guten Tag Erika," in await _render(reset_type)

    async def test_greets_without_a_name(self, reset_type: PasswordResetType) -> None:
        assert "Guten Tag," in await _render(reset_type, user_name="")

    async def test_escapes_the_name(self, reset_type: PasswordResetType) -> None:
        assert "<b>" not in await _render(reset_type, user_name="<b>x</b>")

    async def test_colors_come_from_the_theme(
        self, reset_type: PasswordResetType
    ) -> None:
        body = await _render(reset_type)

        colors = set(re.findall(r"#[0-9a-f]{6}\b", body, re.IGNORECASE))

        assert colors
        assert {c for c in colors if c.casefold() not in THEME_COLORS} == set()
