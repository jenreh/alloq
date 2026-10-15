"""Login in the style of the desktop splash screen.

Soft mesh background, app icon and name, below a small card with email and
password and the single sign-on buttons. The sign-in itself is appkit's
`LoginState`.
"""

from typing import Final

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.shell import desktop_handlers
from alloq_commons.components.splash import splash
from alloq_commons.components.toolbar import DRAG
from alloq_commons.desktop import is_desktop

import appkit_mantine as mn
from appkit_user.authentication.components.login import _icon_src, oauth_button
from appkit_user.authentication.states import LOGIN_ROUTE, LoginState
from appkit_user.configuration import OAuthProvider

from app.desktop.login_state import DesktopLoginState

ICON_PX: Final = 72
CARD_WIDTH: Final = "340px"
SSO_BUTTON: Final = {
    "variant": "default",
    "size": "sm",
    "h": 34,
    "radius": "md",
    "fw": 500,
    "justify": "space-between",
    "full_width": True,
}


def _identity() -> rx.Component:
    return mn.stack(
        rx.image(
            src=rx.asset("img/alloq_icon.svg"),
            alt="",
            width=f"{ICON_PX}px",
            height=f"{ICON_PX}px",
            draggable=False,
            style={
                "padding": "14px",
                "borderRadius": "18px",
                "background": "#FFFFFF",
                "boxShadow": (
                    "0 0 0 0.5px rgba(0,0,0,0.08), 0 10px 24px rgba(0,40,110,0.16)"
                ),
            },
            custom_attrs=DRAG,
        ),
        mn.text("alloq", fz="20px", fw=650, lts="-0.015em", c=theme.TEXT),
        mn.text("Ressourcenplanung", fz="13px", c=theme.TEXT_MUTED, mt=-10),
        align="center",
        gap=12,
        custom_attrs=DRAG,
    )


def _password_form() -> rx.Component:
    return rx.form(
        mn.stack(
            rx.cond(
                LoginState.error_message,
                mn.alert(
                    LoginState.error_message,
                    color="red",
                    variant="light",
                    radius="md",
                    p="8px 10px",
                    fz="12.5px",
                ),
            ),
            mn.text_input(
                name="username",
                label="E-Mail",
                placeholder="name@firma.de",
                auto_focus=True,
                required=True,
                size="sm",
                radius="md",
                custom_attrs={"autoComplete": "username", "type": "email"},
            ),
            mn.password_input(
                name="password",
                label="Passwort",
                required=True,
                size="sm",
                radius="md",
                custom_attrs={"autoComplete": "current-password"},
            ),
            mn.button(
                "Anmelden",
                type="submit",
                size="sm",
                h=34,
                radius="md",
                full_width=True,
                mt=4,
                loading=LoginState.is_loading,
            ),
            rx.link(
                "Passwort vergessen?",
                href="/password-reset",
                font_size="12.5px",
                color=theme.ACCENT,
                align_self="center",
            ),
            gap=10,
        ),
        on_submit=LoginState.login_with_password,
        width="100%",
    )


def _single_sign_on() -> rx.Component:
    return rx.cond(
        LoginState.enable_azure_oauth | LoginState.enable_github_oauth,
        mn.stack(
            mn.divider(label="oder", label_position="center"),
            oauth_button(
                provider=OAuthProvider.AZURE,
                text="Mit Microsoft anmelden",
                icon_light=_icon_src("microsoft.svg"),
                icon_dark=_icon_src("microsoft_dark.svg"),
                enabled_var=LoginState.enable_azure_oauth,
                **SSO_BUTTON,
            ),
            oauth_button(
                provider=OAuthProvider.GITHUB,
                text="Mit GitHub anmelden",
                icon_light=_icon_src("GitHub_light.svg"),
                icon_dark=_icon_src("GitHub_dark.svg"),
                enabled_var=LoginState.enable_github_oauth,
                **SSO_BUTTON,
            ),
            gap=8,
        ),
    )


def _desktop_sign_in() -> rx.Component:
    """Desktop app: Microsoft only; the account also opens the database."""
    return mn.stack(
        rx.cond(
            DesktopLoginState.error_message,
            mn.alert(
                DesktopLoginState.error_message,
                color="red",
                variant="light",
                radius="md",
                p="8px 10px",
                fz="12.5px",
            ),
        ),
        mn.text(
            "Melde dich mit deinem Microsoft-Konto an. Die Anmeldung öffnet "
            "sich im Browser.",
            fz="13px",
            c=theme.TEXT_MUTED,
            ta="center",
        ),
        mn.button(
            "Mit Microsoft anmelden",
            left_section=mn.image(src=_icon_src("microsoft.svg"), w=18, h=18),
            size="sm",
            h=34,
            radius="md",
            full_width=True,
            loading=DesktopLoginState.is_loading,
            on_click=DesktopLoginState.sign_in_with_microsoft,
        ),
        gap=12,
    )


def _card_content() -> rx.Component:
    if is_desktop():
        return _desktop_sign_in()
    return mn.stack(_password_form(), _single_sign_on(), gap=16)


def login_view() -> rx.Component:
    return mn.box(
        splash() if is_desktop() else rx.fragment(),
        mn.stack(
            _identity(),
            mn.box(
                _card_content(),
                w=CARD_WIDTH,
                maw="calc(100vw - 32px)",
                p=20,
                style={
                    "background": theme.SURFACE,
                    "borderRadius": theme.RADIUS,
                    "boxShadow": theme.PANE_SHADOW,
                },
            ),
            align="center",
            gap=28,
        ),
        custom_attrs={**DRAG, "role": "main"},
        style={
            "minHeight": "100dvh",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "padding": "32px 16px",
            "background": theme.token("splash-background"),
        },
    )


def create_login_page(route: str = LOGIN_ROUTE, title: str = "Anmelden") -> None:
    rx.page(
        route=route,
        title=title,
        on_load=desktop_handlers([LoginState.clear_session_storage_token]),
    )(login_view)
