from typing import Final

import reflex as rx

from appkit_commons.registry import service_registry

from app.components.navbar_component import (
    admin_sidebar_item,
    border_radius,
    navbar,
)
from app.configuration import AppConfig

_config = service_registry().get(AppConfig)
VERSION: Final[str] = (
    f"{_config.version}-{_config.environment}"
    if _config.environment
    else _config.version
)


def navbar_header() -> rx.Component:
    return rx.hstack(
        rx.image(
            "/img/logo.svg",
            class_name="h-[54px]",
            margin_top="1.2em",
            margin_left="0px",
        ),
        rx.heading("AppKit", size="8", margin_top="36px", margin_left="6px"),
        rx.spacer(),
        align="center",
        justify="start",
        width="100%",
        padding="0.35em",
        margin_bottom="0",
        margin_top="-0.5em",
    )


def navbar_admin_items() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.icon("settings", size=18),
            rx.text("Administration"),
            align="center",
            border_radius=border_radius,
            width="100%",
            spacing="2",
            padding="0.35em",
            margin_top="1em",
        ),
        admin_sidebar_item(
            label="Benutzer",
            icon="users",
            url="/admin/users",
        ),
        width="95%",
        spacing="1",
    )


def navbar_items() -> rx.Component:
    return rx.vstack(
        # rx.text("Demos", size="2", weight="bold", style=sub_heading_styles),
        # sidebar_item(
        #     label="Assistent",
        #     icon="bot-message-square",
        #     url="/assistant",
        # ),
        rx.spacer(min_height="1em"),
        spacing="1",
        width="95%",
        # margin_top="-1em",
    )


def app_navbar() -> rx.Component:
    return navbar(
        navbar_header=navbar_header(),
        navbar_items=navbar_items(),
        navbar_admin_items=navbar_admin_items(),
        version=VERSION,
    )
