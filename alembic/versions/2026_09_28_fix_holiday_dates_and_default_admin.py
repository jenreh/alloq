"""Fix 2026 NRW holiday seed dates and flag the seeded default admin.

The public_holidays seed placed Pfingstsonntag, Pfingstmontag and Fronleichnam
2026 one month late (Easter 2026 is April 5, so they fall on May 24, May 25 and
June 4). Only rows still carrying the wrong seed date are corrected.

The baseline seeds an ``admin`` account whose password hash is committed to
git. While that hash is unchanged the account is flagged with
``needs_password_reset`` so it shows up as requiring a new password.

Revision ID: cc44dd55ee66
Revises: bb33cc44dd55
Create Date: 2026-09-28 00:00:00.000000

"""

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa

from alembic import op

revision: str = "cc44dd55ee66"
down_revision: str | None = "bb33cc44dd55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (name, wrong seed date, correct date)
HOLIDAY_DATE_FIXES: list[tuple[str, date, date]] = [
    ("Pfingstsonntag", date(2026, 6, 24), date(2026, 5, 24)),
    ("Pfingstmontag", date(2026, 6, 25), date(2026, 5, 25)),
    ("Fronleichnam", date(2026, 7, 4), date(2026, 6, 4)),
]

DEFAULT_ADMIN_EMAIL = "admin"
# The public hash already committed in the baseline, used only to recognise an
# account whose password was never rotated.
DEFAULT_ADMIN_PASSWORD_HASH = (
    "scrypt:32768:8:1$bIA8HVQhPyudwZyV$76d044d2322d395a3a9c95b29337c0c4d24e2426d86d"  # noqa: S105  # pragma: allowlist secret  # gitleaks:allow
    "246cc72095fe2455be0540590ecea3c4d433262ea9d9aaa44eaa285363eed568451895ef2565"
    "2911a2dc"
)

# An admin may already have added the correct row by hand: drop the stale
# duplicate instead of creating a second row for the same holiday.
_DELETE_DUPLICATE = sa.text(
    "DELETE FROM public_holidays "
    "WHERE name = :name AND date = :old_date AND state_code = 'NRW' "
    "AND EXISTS (SELECT 1 FROM public_holidays AS other "
    "WHERE other.name = :name AND other.date = :new_date "
    "AND other.state_code = 'NRW')"
)
_UPDATE_HOLIDAY_DATE = sa.text(
    "UPDATE public_holidays SET date = :new_date "
    "WHERE name = :name AND date = :old_date AND state_code = 'NRW'"
)


def _move_holidays(*, forward: bool) -> None:
    bind = op.get_bind()
    for name, wrong, correct in HOLIDAY_DATE_FIXES:
        old_date, new_date = (wrong, correct) if forward else (correct, wrong)
        params = {"name": name, "old_date": old_date, "new_date": new_date}
        bind.execute(_DELETE_DUPLICATE, params)
        bind.execute(_UPDATE_HOLIDAY_DATE, params)


def upgrade() -> None:
    _move_holidays(forward=True)
    op.get_bind().execute(
        sa.text(
            "UPDATE auth_users SET needs_password_reset = true "
            "WHERE email = :email AND _password = :password_hash"
        ),
        {
            "email": DEFAULT_ADMIN_EMAIL,
            "password_hash": DEFAULT_ADMIN_PASSWORD_HASH,
        },
    )


def downgrade() -> None:
    # The admin flag is left in place on purpose: un-flagging a known password
    # would not restore any meaningful prior state.
    _move_holidays(forward=False)
