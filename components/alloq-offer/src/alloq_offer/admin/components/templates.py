"""Tab "Vorlagen": draft outline, Word layout, publishing and versions."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.sortable import sortable_item, sortable_list
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.admin.states.template_admin_state import (
    UPLOAD_ID,
    TemplateAdminState,
)
from alloq_offer.workshop.components.chapters.labels import TYPE_SHORT, by_type

Row = ObjectVar[dict[str, Any]]

TEMPLATE_LABEL = "Vorlage"
OUTLINE_TITLE = "Gliederung (Entwurf)"
OUTLINE_HINT = (
    "Änderungen gelten erst nach dem Veröffentlichen und nur für neue Angebote. "
    "Bestehende Angebote behalten ihre Version."
)
ADD_BLOCK = "Baustein hinzufügen"
TITLE_PLACEHOLDER = "Titel des Bausteins"
REQUIRED = "Pflicht"
LEVEL_OPTIONS = [
    {"value": "", "label": "Wie Baustein"},
    {"value": "1", "label": "Kapitel"},
    {"value": "2", "label": "Unterkapitel"},
]
REMOVE = "Aus der Gliederung entfernen"
INACTIVE = "Baustein inaktiv"
LAYOUT_TITLE = "Word-Layout"
LAYOUT_HINT = (
    "Eine .docx-Datei mit genau einem Absatz [[KAPITEL]]. Kommentare, Autoren "
    "und Verknüpfungen werden beim Hochladen entfernt."
)
DROP_TEXT = "Word-Datei hier ablegen oder klicken"
FRAME_BEFORE = "Vor den Kapiteln"
FRAME_AFTER = "Nach den Kapiteln"
NO_LAYOUT = "Noch kein Layout hochgeladen."
PUBLISH = "Veröffentlichen"
PUBLISH_HINT = "Erzeugt die nächste Version; neue Angebote nutzen sie."
VERSIONS_TITLE = "Versionen"
NO_VERSIONS = "Noch keine Version veröffentlicht."
DRAG_HINT = (
    "Mit der Leertaste aufnehmen, mit den Pfeiltasten verschieben und mit der "
    "Leertaste ablegen; Escape bricht ab."
)


def _entry(entry: Row) -> rx.Component:
    entry_id = entry["id"].to(int)
    return mn.group(
        rx.el.span(rx.icon("grip-vertical", size=14), class_name="aq-doc-grip"),
        mn.text_input(
            default_value=entry["title_override"].to(str),
            placeholder=entry["block_title"].to(str),
            on_blur=lambda title: TemplateAdminState.set_entry_title(  # ty: ignore[invalid-argument-type]
                entry_id, title
            ),
            custom_attrs={"maxLength": 255},
            key=entry["id"].to(str) + "-" + entry["title_override"].to(str),
            size="xs",
            class_name="aq-doc-grow",
        ),
        rx.el.span(by_type(entry["type"], TYPE_SHORT), class_name="aq-doc-type"),
        rx.cond(
            ~entry["active"].to(bool),
            mn.badge(INACTIVE, color="gray", variant="light", size="xs"),
        ),
        mn.native_select(
            data=LEVEL_OPTIONS,
            value=rx.cond(
                entry["level_override"].to(int) > 0,
                entry["level_override"].to(str),
                "",
            ),
            on_change=lambda level: TemplateAdminState.set_entry_level(  # ty: ignore[invalid-argument-type]
                entry_id, level
            ),
            size="xs",
            w=130,
        ),
        mn.switch(
            label=REQUIRED,
            checked=entry["required"].to(bool),
            on_change=lambda value: TemplateAdminState.set_required(  # ty: ignore[invalid-argument-type]
                entry_id, value
            ),
            size="xs",
        ),
        mn.action_icon(
            rx.icon("x", size=14),
            variant="subtle",
            color="gray",
            aria_label=REMOVE,
            on_click=TemplateAdminState.remove_entry(entry_id),
        ),
        gap=8,
        wrap="nowrap",
        class_name="aq-admin-entry",
    )


def _outline() -> rx.Component:
    return mn.stack(
        mn.text(OUTLINE_TITLE, fz="13px", fw=650),
        mn.text(OUTLINE_HINT, fz="12px", c=theme.TEXT_MUTED),
        sortable_list(
            rx.foreach(
                TemplateAdminState.outline,
                lambda entry, index: sortable_item(
                    _entry(entry),
                    item_id=entry["id"].to(str),
                    index=index,
                    class_name="aq-doc-sortable-item",
                ),
            ),
            ids=TemplateAdminState.entry_ids,
            version=TemplateAdminState.order_version,
            droppable_id="template-outline",
            instructions=DRAG_HINT,
            on_reorder=TemplateAdminState.reorder,
        ),
        mn.select(
            data=TemplateAdminState.library,
            value="",
            placeholder=ADD_BLOCK,
            on_change=TemplateAdminState.add_block,
            searchable=True,
            disabled=TemplateAdminState.library.length() == 0,
            size="xs",
            w=280,
        ),
        gap=10,
        p=16,
        style=theme.CARD,
        class_name="aq-doc-grow aq-admin-outline",
    )


def _frame(title: str, entries: rx.Var) -> rx.Component:
    return mn.stack(
        mn.text(title, fz="12px", fw=600),
        rx.foreach(entries, lambda heading: mn.text(heading, fz="12px")),
        gap=2,
    )


def _layout() -> rx.Component:
    template = TemplateAdminState.template
    return mn.stack(
        mn.text(LAYOUT_TITLE, fz="13px", fw=650),
        mn.text(LAYOUT_HINT, fz="12px", c=theme.TEXT_MUTED),
        rx.cond(
            template["draft_layout_blob_id"].to(int) > 0,
            mn.group(
                _frame(FRAME_BEFORE, template["frame_before"].to(list[str])),
                _frame(FRAME_AFTER, template["frame_after"].to(list[str])),
                align="flex-start",
                gap=24,
            ),
            mn.text(NO_LAYOUT, fz="12px", c=theme.WARNING),
        ),
        rx.upload(
            mn.text(DROP_TEXT, fz="13px", c=theme.TEXT_MUTED, ta="center"),
            id=UPLOAD_ID,
            accept={
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document": [".docx"]
            },
            multiple=False,
            no_keyboard=False,
            on_drop=TemplateAdminState.handle_upload(  # ty: ignore[no-matching-overload]
                rx.upload_files(upload_id=UPLOAD_ID)
            ),
            border=f"1px dashed {theme.BORDER}",
            border_radius="10px",
            padding="14px",
            cursor="pointer",
        ),
        gap=10,
    )


def _version(version: Row) -> rx.Component:
    return mn.group(
        mn.text("Version " + version["number"].to(str), fz="12px", fw=600),
        mn.text(
            version["created"].to(str) + " · " + version["published_by"].to(str),
            fz="12px",
            c=theme.TEXT_MUTED,
        ),
        mn.text(
            version["chapters"].to(str) + " Kapitel", fz="12px", c=theme.TEXT_MUTED
        ),
        gap=8,
    )


def _side() -> rx.Component:
    return mn.stack(
        _layout(),
        mn.stack(
            mn.button(PUBLISH, on_click=TemplateAdminState.publish),
            mn.text(PUBLISH_HINT, fz="12px", c=theme.TEXT_MUTED),
            gap=4,
        ),
        mn.stack(
            mn.text(VERSIONS_TITLE, fz="13px", fw=650),
            rx.cond(
                TemplateAdminState.versions.length() > 0,
                rx.foreach(TemplateAdminState.versions, _version),
                mn.text(NO_VERSIONS, fz="12px", c=theme.TEXT_MUTED),
            ),
            gap=6,
        ),
        gap=20,
        p=16,
        w=360,
        style=theme.CARD,
    )


def templates_tab() -> rx.Component:
    return mn.stack(
        rx.cond(
            TemplateAdminState.templates.length() > 1,
            mn.select(
                label=TEMPLATE_LABEL,
                data=TemplateAdminState.template_options,
                value=TemplateAdminState.template_id.to(str),
                on_change=TemplateAdminState.select_template,
                size="xs",
                w=280,
            ),
        ),
        mn.group(_outline(), _side(), align="flex-start", wrap="wrap", gap=16),
        gap=12,
    )
