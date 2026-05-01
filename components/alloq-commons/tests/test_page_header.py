import reflex as rx
from alloq_commons.components.page_header import page_header


class TestPageHeader:
    def test_returns_component_with_string_nav_path(self) -> None:
        result = page_header(
            nav_path="Setting",
            title="Account Settings",
            description="Manage your preferences, security, and connected tools.",
        )

        assert isinstance(result, rx.Component)

    def test_returns_component_with_multiple_nav_segments(self) -> None:
        result = page_header(
            nav_path=["Setting", "Account"],
            title="Account Settings",
            description="Manage your preferences.",
        )

        assert isinstance(result, rx.Component)
