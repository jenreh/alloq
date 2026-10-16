"""Faked Microsoft sign-in for development."""

import os
from unittest.mock import patch

from app.desktop import login_state
from app.desktop.fake import FakeEntraSignIn, fake_email
from app.desktop.profile import DESKTOP_ROOT_ENV, FAKE_ENV


def test_fake_email_only_outside_the_bundle() -> None:
    with patch.dict(os.environ, {FAKE_ENV: " ada@example.com "}):
        os.environ.pop(DESKTOP_ROOT_ENV, None)
        assert fake_email() == "ada@example.com"
    with patch.dict(os.environ, {FAKE_ENV: "ada@example.com", DESKTOP_ROOT_ENV: "/a"}):
        assert fake_email() is None
    with patch.dict(os.environ, {}, clear=True):
        assert fake_email() is None


def test_fake_sign_in_returns_the_configured_account() -> None:
    sign_in = FakeEntraSignIn("ada@example.com")
    assert sign_in.account is None
    account = sign_in.sign_in_interactively()
    assert account.email == "ada@example.com"
    assert sign_in.account == account
    sign_in.sign_out()
    assert sign_in.account is None


def test_get_sign_in_uses_the_fake() -> None:
    login_state.get_sign_in.cache_clear()
    try:
        with patch.object(login_state, "fake_email", return_value="a@b.c"):
            assert isinstance(login_state.get_sign_in(), FakeEntraSignIn)
    finally:
        login_state.get_sign_in.cache_clear()


def test_fake_profile_is_never_bundled() -> None:
    from tests.test_desktop_login import _desktop_script  # noqa: PLC0415

    assert "config.desktop_fake.yaml" not in _desktop_script().CONFIG_FILES


def test_profile_constants_match_the_components() -> None:
    from alloq_commons import desktop  # noqa: PLC0415

    from app.desktop import profile  # noqa: PLC0415

    assert profile.DESKTOP_ENV == desktop.DESKTOP_ENV
    assert profile.DESKTOP_ROOT_ENV == desktop.DESKTOP_ROOT_ENV
