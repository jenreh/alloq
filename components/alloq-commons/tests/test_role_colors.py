from alloq_commons.models.employee import Employee
from alloq_commons.role_colors import (
    AVATAR_FALLBACK_COLOR,
    DEFAULT_ROLE_COLOR,
    role_avatar_color,
    role_color,
)


def test_role_color_is_stable_and_case_insensitive() -> None:
    assert role_color("AI Architect") == role_color(" ai architect ")


def test_role_color_differs_per_role() -> None:
    names = ["Project Manager", "AI Architect", "Data Scientist", "AI Engineer"]
    assert len({role_color(n) for n in names}) == len(names)


def test_role_color_empty_uses_default() -> None:
    assert role_color("") == DEFAULT_ROLE_COLOR


def test_role_avatar_color_is_stable_per_role() -> None:
    assert role_avatar_color(3) == role_avatar_color(3)
    assert role_avatar_color(3).startswith("hsl(")


def test_role_avatar_color_is_unique_per_role() -> None:
    role_ids = range(1, 21)
    assert len({role_avatar_color(r) for r in role_ids}) == len(role_ids)


def test_role_avatar_color_without_role_is_neutral() -> None:
    assert role_avatar_color(None) == AVATAR_FALLBACK_COLOR
    assert role_avatar_color(0) == AVATAR_FALLBACK_COLOR


def test_employee_avatar_color_follows_key_role() -> None:
    assert Employee(key_role_id=4).avatar_color == role_avatar_color(4)
    assert Employee().avatar_color == AVATAR_FALLBACK_COLOR
