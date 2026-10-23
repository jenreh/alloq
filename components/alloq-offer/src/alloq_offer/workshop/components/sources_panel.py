"""Sources panel of the draft tab: list, drop area and pasted text."""

from collections.abc import Sequence
from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.list_view import inspector, inspector_section
from alloq_commons.components.modal_layout import (
    MODAL_CLASS,
    modal_footer,
    modal_form_layout,
)
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.workshop.services.sources import TEXT_EXTENSIONS
from alloq_offer.workshop.states.sources_state import UPLOAD_ID, SourcesState

SOURCES_TITLE = "Quellen"
NO_SOURCES = "Noch keine Quellen. Fügen Sie Texte, E-Mails oder Dokumente hinzu."
SOURCES_HINT = (
    "Lücken wie nicht ausgewertete Bilder oder fehlende OCR bleiben sichtbar. "
    "Neue Quellen ändern einen bestehenden Entwurf nur als Vorschlag."
)
DROP_TEXT = "E-Mails, Mitschnitte, Konzepte oder Folien hier ablegen"
ADD_TEXT = "Text einfügen"
PASTE_TITLE = "Text als Quelle einfügen"
PASTE_SUBMIT = "Quelle hinzufügen"
RETRY_LABEL = "Erneut versuchen"
UPLOAD_ACCEPT: dict[str, Sequence] = {
    "message/rfc822": [".eml"],
    "text/*": [*TEXT_EXTENSIONS, ".html", ".htm"],
    "application/pdf": [".pdf"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        ".docx"
    ],
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": [
        ".pptx"
    ],
    "audio/*": [".wav", ".mp3", ".m4a"],
}
STATUS_POLL_MS = 3000


def _drop_area() -> rx.Component:
    return rx.upload(
        mn.text(DROP_TEXT, fz="13px", c=theme.TEXT_MUTED, ta="center"),
        id=UPLOAD_ID,
        accept=UPLOAD_ACCEPT,
        multiple=True,
        no_keyboard=False,
        on_drop=SourcesState.handle_upload(  # ty: ignore[no-matching-overload]
            rx.upload_files(upload_id=UPLOAD_ID)
        ),
        border=f"1px dashed {theme.BORDER}",
        border_radius="10px",
        padding="14px",
        cursor="pointer",
    )


def _source_row(source: ObjectVar[dict[str, Any]]) -> rx.Component:
    return mn.group(
        mn.checkbox(
            checked=source["included"],
            disabled=~source["usable"],
            on_change=lambda checked: SourcesState.toggle_source(  # ty: ignore[invalid-argument-type]
                source["id"], checked
            ),
        ),
        mn.stack(
            mn.text(source["name"], fw=600, fz="13px"),
            mn.text(
                source["summary"],
                fz="12px",
                c=rx.cond(source["ok"], theme.POSITIVE, theme.WARNING),
            ),
            gap=2,
            style={"minWidth": "0", "flex": "1"},
        ),
        rx.cond(
            source["retryable"],
            mn.button(
                RETRY_LABEL,
                variant="subtle",
                size="compact-xs",
                on_click=SourcesState.retry_source(source["id"]),
            ),
        ),
        wrap="nowrap",
        align="flex-start",
        p=10,
        style={"borderRadius": "8px", "background": theme.SURFACE_MUTED},
    )


def _paste_modal() -> rx.Component:
    return mn.modal(
        modal_form_layout(
            content=mn.stack(
                mn.text_input(
                    name="title",
                    label="Bezeichnung",
                    placeholder="z.B. Notizen aus dem Telefonat",
                    custom_attrs={"maxLength": 255},
                ),
                mn.textarea(
                    name="text",
                    label="Text",
                    required=True,
                    autosize=True,
                    min_rows=8,
                    max_rows=16,
                ),
                gap="md",
            ),
            footer=modal_footer(PASTE_SUBMIT, SourcesState.close_paste),
            on_submit=SourcesState.add_pasted_text,
            reset_on_submit=True,
        ),
        title=PASTE_TITLE,
        opened=SourcesState.paste_open,
        on_close=SourcesState.close_paste,
        size="lg",
        centered=True,
        class_name=MODAL_CLASS,
        overlay_props={"backgroundOpacity": 0.5, "blur": 4},
    )


def sources_panel() -> rx.Component:
    return inspector(
        inspector_section(
            SOURCES_TITLE,
            mn.group(
                mn.button(
                    ADD_TEXT,
                    variant="subtle",
                    size="compact-sm",
                    on_click=SourcesState.open_paste,
                ),
                justify="flex-end",
            ),
            _drop_area(),
            rx.cond(
                SourcesState.is_empty,
                mn.text(NO_SOURCES, fz="13px", c=theme.TEXT_MUTED),
                mn.stack(rx.foreach(SourcesState.sources, _source_row), gap=6),
            ),
            mn.text(SOURCES_HINT, fz="12px", c=theme.TEXT_MUTED, lh="1.5"),
            rx.cond(
                SourcesState.has_working,
                rx.moment(
                    interval=STATUS_POLL_MS,
                    on_change=SourcesState.load_sources,
                    display="none",
                ),
            ),
        ),
        _paste_modal(),
        label=SOURCES_TITLE,
    )
