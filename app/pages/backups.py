"""Backup page: uncontrolled credentials are submitted only over protected HTTP."""

import reflex as rx
from alloq_commons import theme
from alloq_commons.access import backup_only, no_access
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar

import appkit_mantine as mn


class BackupForm(rx.el.Div):
    """A native form without Reflex's automatic submit serialization."""

    tag = "form"


def password_fields(prefix: str) -> list[rx.Component]:
    return [
        mn.password_input(
            label="Ihr aktuelles Alloq-Passwort",
            name="password",
            required=True,
            id=f"{prefix}-password",
            custom_attrs={"autoComplete": "current-password"},
        ),
        mn.password_input(
            label="Separate Sicherungspassphrase",
            name="passphrase",
            required=True,
            id=f"{prefix}-passphrase",
            description="Mindestens 24 Zeichen. Getrennt vom Alloq-Passwort speichern.",
            custom_attrs={"autoComplete": "off", "minLength": 24, "maxLength": 256},
        ),
    ]


def backup_forms() -> rx.Component:
    config = rx.config.get_config()
    api = str(config.api_url).rstrip("/") + config.backend_path + "/api/admin/backups"
    return mn.stack(
        rx.script(src=rx.asset("js/database-backup.js")),
        mn.text(
            "Jede Sicherungsaktion erfordert Ihr lokales Alloq-Passwort. "
            "Dies gilt auch bei einer Anmeldung über Microsoft.",
        ),
        BackupForm.create(
            mn.stack(
                mn.title("Sicherung exportieren", order=3),
                *password_fields("backup-export"),
                mn.button(
                    "Sicherungspassphrase erzeugen", type="button", id="backup-generate"
                ),
                mn.password_input(
                    label="Sicherungspassphrase wiederholen",
                    name="passphrase_confirmation",
                    required=True,
                    custom_attrs={"autoComplete": "off"},
                ),
                mn.text(
                    "Passphrase sicher aufbewahren. "
                    "Ohne sie ist keine Wiederherstellung möglich."
                ),
                mn.button("Sicherung exportieren", type="submit"),
                gap="md",
            ),
            id="backup-export",
            custom_attrs={
                "data-backup-api": api,
                "method": "post",
                "action": api + "/export",
            },
        ),
        mn.divider(),
        BackupForm.create(
            mn.stack(
                mn.title("Sicherung importieren", order=3),
                mn.text(
                    "Ein Import ersetzt alle aktuellen Daten und Benutzerkonten. "
                    "Alle Benutzer werden abgemeldet. Melden Sie sich anschließend "
                    "mit einem Konto aus der Sicherung erneut an.",
                ),
                rx.el.label("Verschlüsselte ZIP-Sicherung", html_for="backup-archive"),
                rx.el.input(
                    type="file",
                    name="archive",
                    id="backup-archive",
                    accept=".zip",
                    required=True,
                ),
                *password_fields("backup-import"),
                mn.button("Sicherung prüfen", type="submit", name="inspect"),
                rx.el.div(id="backup-metadata", custom_attrs={"role": "status"}),
                mn.text("Nach der Prüfung zum Bestätigen DATENBANK ERSETZEN eingeben:"),
                mn.text_input(
                    name="confirmation",
                    id="backup-confirmation",
                    custom_attrs={"autoComplete": "off"},
                ),
                mn.button(
                    "Datenbank ersetzen",
                    type="submit",
                    id="backup-restore",
                    disabled=True,
                ),
                gap="md",
            ),
            id="backup-import",
            custom_attrs={
                "data-backup-api": api,
                "method": "post",
                "action": api + "/inspect",
            },
        ),
        rx.el.p(
            id="backup-status", custom_attrs={"role": "status", "aria-live": "polite"}
        ),
        gap="lg",
        style=theme.CARD,
        p="lg",
        w="100%",
        maw=760,
    )


def create_backups_page(sidebar: rx.Component) -> rx.Component:
    @app_page(
        route="/admin/backups",
        title="Datenbanksicherung",
        sidebar=sidebar,
        admin_only=True,
        toolbar=window_toolbar(
            "Datenbanksicherung", "Administration · Sichern und Wiederherstellen"
        ),
    )
    def _backups_page() -> rx.Component:
        return backup_only(backup_forms(), fallback=no_access())

    return _backups_page
