"""Backup access always needs the administrator switch and the explicit role."""

from types import SimpleNamespace

import pytest
import reflex as rx
from alloq_commons.access import backup_only, can_manage_backups
from alloq_commons.roles import ALL_ROLES, DATABASE_BACKUP_ROLE


@pytest.mark.parametrize(
    ("admin", "roles", "allowed"),
    [
        (False, [], False),
        (True, [], False),
        (False, ["database_backup"], False),
        (True, ["database_backup"], True),
    ],
)
def test_backup_permission_requires_both(
    admin: bool, roles: list[str], allowed: bool
) -> None:
    user = SimpleNamespace(is_admin=admin, roles=roles)
    assert can_manage_backups(user) is allowed


def test_role_is_available_and_identifiers_are_unique() -> None:
    assert DATABASE_BACKUP_ROLE in ALL_ROLES
    assert len({role.name for role in ALL_ROLES}) == len(ALL_ROLES)
    assert len({role.id for role in ALL_ROLES}) == len(ALL_ROLES)


def test_hidden_sidebar_item_does_not_render_a_permission_error_panel() -> None:
    assert "Sie haben nicht die notwendigen" not in str(backup_only(rx.text("link")))
