"""Tab "Export": Word draft and final version, and the list of made files."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.list_view import empty_list, inspector_section
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.workshop.states.export_state import ExportState

Row = ObjectVar[dict[str, Any]]

DRAFT_TITLE = "Word-Entwurf"
DRAFT_TEXT = (
    "Mit sichtbarem Entwurfsstatus. Offene Punkte und Annahmen werden am Ende "
    "aufgeführt. Ein Entwurf ist immer möglich."
)
DRAFT_BUTTON = "Entwurf erzeugen"
FINAL_TITLE = "Finale Fassung"
FINAL_TEXT = (
    "Nur ohne offene Blocker und mit bestätigter Kalkulation, wenn ein Preis "
    "erforderlich ist. Interne Prüfhinweise werden nicht ausgegeben."
)
FINAL_BUTTON = "Finale Fassung erzeugen"
CONFIRM_LABEL = "Ich bestätige den gesamten aktuellen Stand."
BLOCKED_TITLE = "Die finale Fassung ist noch nicht möglich:"
LIST_TITLE = "Erzeugte Dateien"
EMPTY = "Noch keine Datei erzeugt."
DOWNLOAD = "Herunterladen"
NO_SYNC = (
    "Änderungen an einer heruntergeladenen Word-Datei werden nicht in die "
    "Werkstatt zurückübernommen. Eine erzeugte Datei bleibt unverändert."
)
BLOCKERS = " offene Blocker"
POLL_MS = 3000
STATUS_COLORS = {"fertig": "green", "in Arbeit": "blue", "fehlgeschlagen": "red"}


def _export_row(row: Row) -> rx.Component:
    return mn.group(
        mn.stack(
            mn.group(
                mn.text(row["filename"].to(str), fz="13px", fw=600),
                mn.badge(row["kind"].to(str), variant="outline", size="xs"),
                mn.badge(
                    row["status"].to(str),
                    color=rx.match(
                        row["status"].to(str), *STATUS_COLORS.items(), "gray"
                    ),  # ty: ignore[invalid-argument-type]
                    variant="light",
                    size="xs",
                ),
                gap=8,
            ),
            mn.text(
                row["created"].to(str) + " · " + row["created_by"].to(str),
                fz="12px",
                c=theme.TEXT_MUTED,
            ),
            rx.cond(
                row["failed"].to(bool),
                mn.text(row["error"].to(str), fz="12px", c=theme.NEGATIVE),
            ),
            gap=2,
        ),
        rx.cond(
            row["ready"].to(bool),
            mn.button(
                DOWNLOAD,
                variant="default",
                size="compact-sm",
                on_click=ExportState.download_export(row["id"].to(int)),
            ),
        ),
        justify="space-between",
        align="center",
        py=8,
        style={"borderTop": f"1px solid {theme.SEPARATOR}"},
    )


def _reasons() -> rx.Component:
    return rx.cond(
        ExportState.reasons.length() > 0,
        mn.stack(
            mn.text(BLOCKED_TITLE, fz="13px", fw=600, c=theme.NEGATIVE),
            rx.foreach(
                ExportState.reasons,
                lambda reason: mn.text(reason, fz="13px", c=theme.NEGATIVE),
            ),
            gap=4,
        ),
    )


def export_tab() -> rx.Component:
    return rx.box(_export_content(), on_mount=ExportState.load_exports)


def _export_content() -> rx.Component:
    return mn.stack(
        mn.group(
            mn.stack(
                inspector_section(
                    DRAFT_TITLE,
                    mn.text(DRAFT_TEXT, fz="13px", c=theme.TEXT_MUTED, lh="1.5"),
                    mn.button(
                        DRAFT_BUTTON,
                        variant="default",
                        on_click=ExportState.export_draft,
                    ),
                ),
                p=18,
                style={**theme.CARD, "flex": "1 1 320px"},
            ),
            mn.stack(
                inspector_section(
                    FINAL_TITLE,
                    mn.text(FINAL_TEXT, fz="13px", c=theme.TEXT_MUTED, lh="1.5"),
                    mn.text(
                        ExportState.open_blockers.to(str) + BLOCKERS,
                        fz="12px",
                        c=theme.TEXT_MUTED,
                    ),
                    mn.checkbox(
                        label=CONFIRM_LABEL,
                        checked=ExportState.confirmed,
                        on_change=ExportState.set_confirmed,
                    ),
                    mn.button(FINAL_BUTTON, on_click=ExportState.export_final),
                ),
                p=18,
                style={**theme.CARD, "flex": "1 1 320px"},
            ),
            align="stretch",
            gap=16,
            wrap="wrap",
        ),
        _reasons(),
        mn.stack(
            inspector_section(
                LIST_TITLE,
                rx.cond(
                    ExportState.exports.length() > 0,
                    mn.stack(rx.foreach(ExportState.exports, _export_row), gap=0),
                    empty_list(EMPTY),
                ),
            ),
            mn.text(NO_SYNC, fz="12px", c=theme.TEXT_MUTED, lh="1.5"),
            p=18,
            gap=12,
            style=theme.CARD,
        ),
        rx.cond(
            ExportState.working,
            rx.moment(
                interval=POLL_MS,
                on_change=ExportState.refresh_exports,
                display="none",
            ),
        ),
        gap=16,
        p=20,
    )
