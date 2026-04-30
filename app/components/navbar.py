from typing import Final

import reflex as rx

import appkit_mantine as mn
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
    return mn.group(
        mn.image(
            src="/img/logo.svg",
            h="54px",
            fit="contain",
        ),
        mn.title("AppKit", order=1),
        justify="start",
        align="center",
        wrap="nowrap",
        gap="12px",
        w="95%",
        mt="0.5em",
    )


def navbar_admin_items() -> rx.Component:
    return mn.stack(
        mn.group(
            rx.icon("settings", size=18),
            mn.text("Administration"),
            align="center",
            gap="sm",
            w="100%",
            style={"border_radius": border_radius, "padding": "0.35em"},
            mt="1em",
        ),
        admin_sidebar_item(
            label="Benutzer",
            icon="users",
            url="/admin/users",
        ),
        w="95%",
        gap="xs",
    )


def navbar_items() -> rx.Component:
    return mn.stack(
        mn.space(h="1em"),
        gap="xs",
        w="95%",
    )


def app_navbar() -> rx.Component:
    return navbar(
        navbar_header=navbar_header(),
        navbar_items=navbar_items(),
        navbar_admin_items=navbar_admin_items(),
        version=VERSION,
    )


def app_navbar_mobile() -> rx.Component:
    return mn.stack(
        navbar_header(),
        navbar_items(),
        navbar_admin_items(),
        mn.text(f"Version: {VERSION}", size="xs", c="dimmed"),
        gap="md",
        p="1rem",
        w="280px",
    )
