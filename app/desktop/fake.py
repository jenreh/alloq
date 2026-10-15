"""Fake Microsoft sign-in for developing and testing the desktop app.

`ALLOQ_FAKE_ENTRA_EMAIL=<email>` skips MSAL: the sign-in button signs in as
that alloq user, and the database uses the local profile's credentials
(profile `desktop_fake`) instead of Entra tokens. Inside the app bundle the
variable is ignored, and the build never ships the `desktop_fake` profile.
"""

import logging
import os

from app.desktop.entra import Account
from app.desktop.profile import FAKE_ENV, in_bundle

logger = logging.getLogger(__name__)


def fake_email() -> str | None:
    """The faked account's email, never inside the app bundle."""
    email = os.environ.get(FAKE_ENV, "").strip()
    if not email or in_bundle():
        return None
    return email


class FakeEntraSignIn:
    """Same surface as `EntraSignIn`, without Microsoft."""

    def __init__(self, email: str) -> None:
        self._email = email
        self._account: Account | None = None
        logger.warning("Desktop sign-in is faked for %s", email)

    @property
    def account(self) -> Account | None:
        return self._account

    def sign_in_silently(self) -> Account:
        self._account = Account(email=self._email, name=self._email, db_user="")
        return self._account

    def sign_in_interactively(self) -> Account:
        return self.sign_in_silently()

    def sign_out(self) -> None:
        self._account = None
