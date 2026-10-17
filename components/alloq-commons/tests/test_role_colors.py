from alloq_commons.role_colors import DEFAULT_ROLE_COLOR, role_color


def test_role_color_is_stable_and_case_insensitive() -> None:
    assert role_color("AI Architect") == role_color(" ai architect ")


def test_role_color_differs_per_role() -> None:
    names = ["Project Manager", "AI Architect", "Data Scientist", "AI Engineer"]
    assert len({role_color(n) for n in names}) == len(names)


def test_role_color_empty_uses_default() -> None:
    assert role_color("") == DEFAULT_ROLE_COLOR
