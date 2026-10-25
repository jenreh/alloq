"""Sources panel of the draft tab: list, drop area and pasted text."""

from collections.abc import Sequence
from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.dialogs import delete_dialog
from alloq_commons.components.document_viewer import document_viewer
from alloq_commons.components.list_view import inspector, inspector_section
from alloq_commons.components.modal_layout import (
    DRAWER_CLASS,
    MODAL_CLASS,
    modal_footer,
    modal_form_layout,
)
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.workshop.services.sources import TEXT_EXTENSIONS
from alloq_offer.workshop.states.briefing_state import BriefingState
from alloq_offer.workshop.states.draft_state import DraftState
from alloq_offer.workshop.states.map_state import MapState
from alloq_offer.workshop.states.sources_state import (
    UPLOAD_ID,
    VIEWER_TAB_ORIGINAL,
    VIEWER_TAB_TEXT,
    SourcesState,
)

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
REVOKE_TITLE = "Quelle zurückziehen"
VIEW_LABEL = "Ansehen"
GAP_LABEL = "Nicht gelesen"
NO_BLOCKS = "Aus dieser Quelle wurde noch nichts gelesen."
ORIGINAL_TAB = "Original"
TEXT_TAB = "Gelesener Text"
RETRY_LABEL = "Erneut versuchen"
READING_TITLE = "Quellen werden gelesen"
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
# Mantine's "sm" checkbox is 20px wide; the status line indents by it plus the gap.
CHECKBOX_SIZE = "sm"
CHECKBOX_PX = 20
HEAD_GAP_PX = 12
# The viewer puts its page rail beside the page only above 768px of container.
VIEWER_DRAWER_SIZE = "min(1120px, 94vw)"
_GROW = {"flex": "1 1 0%", "minHeight": 0}
# Mantine lays Tabs out through these variables and its stylesheet beats a
# class; inline `styles` make the tabs a column whose active panel fills the
# drawer, so the viewer below gets a real height.
VIEWER_TABS_STYLES = {
    "root": {
        "--tabs-display": "flex",
        "--tabs-flex-direction": "column",
        "--tabs-panel-grow": "1",
        **_GROW,
    },
    "panel": {**_GROW, "display": "flex", "flexDirection": "column"},
}


def _read_progress() -> rx.Component:
    """Shown while sources are read; the bar moves as each one finishes."""
    return rx.cond(
        SourcesState.reading,
        mn.stack(
            mn.group(
                mn.text(READING_TITLE, fz="12px", fw=600),
                mn.text(SourcesState.read_label, fz="12px", c=theme.TEXT_MUTED),
                justify="space-between",
            ),
            mn.progress(
                value=SourcesState.read_progress,
                size="sm",
                radius="xl",
                striped=True,
                animated=True,
            ),
            gap=6,
        ),
    )


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
    """Name and actions in one line; the status below uses the full card width."""
    return mn.stack(
        _source_head(source),
        mn.text(
            source["summary"],
            fz="12px",
            c=rx.cond(source["ok"], theme.POSITIVE, theme.WARNING),
            # Starts under the name, not under the checkbox.
            pl=CHECKBOX_PX + HEAD_GAP_PX,
        ),
        gap=6,
        p=10,
        style={"borderRadius": "8px", "background": theme.SURFACE_MUTED},
    )


def _source_head(source: ObjectVar[dict[str, Any]]) -> rx.Component:
    return mn.group(
        mn.checkbox(
            checked=source["included"],
            disabled=~source["usable"],
            size=CHECKBOX_SIZE,
            on_change=lambda checked: SourcesState.toggle_source(  # ty: ignore[invalid-argument-type]
                source["id"], checked
            ),
        ),
        mn.text(
            source["name"],
            fw=600,
            fz="13px",
            style={"minWidth": "0", "flex": "1", "overflowWrap": "anywhere"},
        ),
        mn.action_icon(
            rx.icon("eye", size=16),
            variant="subtle",
            color="gray",
            size="sm",
            on_click=SourcesState.open_viewer(source["id"]),
            aria_label=VIEW_LABEL,
            custom_attrs={"title": VIEW_LABEL},
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
        delete_dialog(
            REVOKE_TITLE,
            source["name"],
            SourcesState.revoke_source(source["id"]),
            icon_button=True,
            variant="subtle",
            color="gray",
            size="sm",
        ),
        gap=HEAD_GAP_PX,
        wrap="nowrap",
        align="flex-start",
    )


def _block(block: ObjectVar[dict[str, Any]]) -> rx.Component:
    return mn.stack(
        mn.group(
            mn.text(block["label"], fz="11px", fw=600, c=theme.TEXT_MUTED),
            rx.cond(
                block["speaker"] != "",
                mn.text(block["speaker"], fz="11px", c=theme.TEXT_MUTED),
            ),
            rx.cond(
                block["gap"],
                mn.badge(GAP_LABEL, color="yellow", variant="light", size="xs"),
            ),
            gap=8,
        ),
        mn.text(
            block["text"],
            fz="13px",
            lh="1.5",
            c=rx.cond(block["gap"], theme.WARNING, theme.TEXT),
        ),
        gap=2,
        py=6,
        style={"borderTop": f"1px solid {theme.SEPARATOR}"},
    )


def _blocks() -> rx.Component:
    return mn.box(
        rx.cond(
            SourcesState.viewer_blocks.length() > 0,
            mn.stack(rx.foreach(SourcesState.viewer_blocks, _block), gap=0),
            mn.text(NO_BLOCKS, fz="13px", c=theme.TEXT_MUTED),
        ),
        class_name="alloq-modal-scroll",
    )


def _original() -> rx.Component:
    return rx.cond(
        SourcesState.viewer_note != "",
        mn.text(SourcesState.viewer_note, fz="13px", c=theme.TEXT_MUTED, p=18),
        document_viewer(
            SourcesState.viewer_kind,
            SourcesState.viewer_encoded,
            SourcesState.viewer_file,
        ),
    )


def _viewer_tabs() -> rx.Component:
    """Original file and extracted text; the viewer mounts only on its tab."""
    return mn.tabs(
        mn.tabs.list(
            mn.tabs.tab(ORIGINAL_TAB, value=VIEWER_TAB_ORIGINAL),
            mn.tabs.tab(TEXT_TAB, value=VIEWER_TAB_TEXT),
            px=26,
        ),
        mn.tabs.panel(_original(), value=VIEWER_TAB_ORIGINAL),
        mn.tabs.panel(_blocks(), value=VIEWER_TAB_TEXT),
        value=SourcesState.viewer_tab,
        on_change=SourcesState.set_viewer_tab,
        custom_attrs={"styles": VIEWER_TABS_STYLES},
    )


def _viewer_drawer() -> rx.Component:
    """Slides in from the right, wide enough for the page rail beside a page."""
    has_original = SourcesState.viewer_kind != ""
    return mn.drawer(
        rx.cond(has_original, _viewer_tabs(), _blocks()),
        title=SourcesState.viewer_title,
        opened=SourcesState.viewer_open,
        on_close=SourcesState.close_viewer,
        position="right",
        size=rx.cond(has_original, VIEWER_DRAWER_SIZE, "lg"),
        offset="15px",
        radius="md",
        keep_mounted=False,
        class_name=DRAWER_CLASS,
        overlay_props={"backgroundOpacity": 0.3, "blur": 3},
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
            _read_progress(),
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
                    on_change=[
                        SourcesState.load_sources,
                        MapState.load_map,
                        BriefingState.load_briefing,
                        DraftState.load_overview,
                    ],
                    display="none",
                ),
            ),
        ),
        _paste_modal(),
        _viewer_drawer(),
        label=SOURCES_TITLE,
    )
