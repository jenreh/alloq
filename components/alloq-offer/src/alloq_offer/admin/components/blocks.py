"""Tab "Kapitelbausteine": the chapter library and its editor."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.modal_layout import MODAL_CLASS, MODAL_OVERLAY
from alloq_commons.components.toolbar import segmented
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.admin.states.block_admin_state import BlockAdminState
from alloq_offer.workshop.components.chapters.editor import chapter_editor
from alloq_offer.workshop.components.chapters.labels import (
    TYPE_LABELS,
    TYPE_OPTIONS,
    by_type,
)
from alloq_offer.workshop.content.schema import BOUND_FIELDS
from alloq_offer.workshop.services.checks import CHAPTER_CHECKS
from alloq_offer.workshop.states.chapter_panel_mixin import GROUP_OPTIONS
from alloq_offer.workshop.states.outline_mixin import LEVEL_OPTIONS

Row = ObjectVar[dict[str, Any]]

NEW_BLOCK = "Neuer Baustein"
EDIT_TITLE = "Kapitelbaustein"
EMPTY = "Es gibt noch keine Kapitelbausteine."
COLUMNS = ("Titel", "Schlüssel", "Typ", "Verwendet in", "Status")
INACTIVE = "inaktiv"
ACTIVE = "aktiv"
KEY_LABEL = "Schlüssel"
KEY_HINT = "Kleinbuchstaben, Ziffern und _; später nicht mehr änderbar."
TITLE_LABEL = "Titel"
TYPE_LABEL = "Kapiteltyp"
LEVEL_LABEL = "Ebene"
START_LABEL = "Startinhalt"
GUIDE_LABEL = "Leitfrage"
RULES_LABEL = "Regeln"
PROMPT_LABEL = "Prompt-Ergänzung"
PROMPT_HINT = "Zusätzliche Anweisung an die KI für dieses Kapitel."
INFO_LABEL = "Pflichtangaben"
CHECKS_LABEL = "Prüfungen"
ACTIVE_LABEL = "Aktiv (im Katalog für neue Kapitel)"
USED_IN = "Verwendet in: "
NOT_USED = "Wird in keiner Vorlage verwendet."
SAVE = "Speichern"
DELETE = "Löschen"
CANCEL = "Abbrechen"
GROUP_LABEL = "Gruppieren nach"
VALUES_LABEL = "Gebundene Werte"
ITEMS_HINT = "Eingabe mit Enter übernehmen"
CHECK_OPTIONS = [{"value": k, "label": v} for k, v in CHAPTER_CHECKS.items()]
VALUE_OPTIONS = [{"value": k, "label": v} for k, v in BOUND_FIELDS.items()]


def _set(name: str) -> Any:
    return lambda value: BlockAdminState.set_field(name, value)  # ty: ignore[invalid-argument-type]


def _row(block: Row) -> rx.Component:
    used = block["used_in"].to(list[str])
    return mn.table.tr(
        mn.table.td(mn.text(block["title"], fz="13px", fw=600)),
        mn.table.td(mn.text(block["key"], fz="12px", ff=theme.FONT_MONO)),
        mn.table.td(by_type(block["chapter_type"], TYPE_LABELS)),
        mn.table.td(mn.text(used.join(", "), fz="12px", c=theme.TEXT_MUTED)),
        mn.table.td(
            rx.cond(
                block["active"].to(bool),
                mn.badge(ACTIVE, color="green", variant="light", size="sm"),
                mn.badge(INACTIVE, color="gray", variant="light", size="sm"),
            )
        ),
        on_click=BlockAdminState.open_edit(block["key"].to(str)),
        class_name="aq-admin-row",
    )


def blocks_table() -> rx.Component:
    return mn.stack(
        mn.group(
            mn.button(NEW_BLOCK, size="xs", on_click=BlockAdminState.open_create),
            justify="flex-end",
        ),
        rx.cond(
            BlockAdminState.blocks.length() > 0,
            mn.table(
                mn.table.thead(
                    mn.table.tr(*(mn.table.th(column) for column in COLUMNS))
                ),
                mn.table.tbody(rx.foreach(BlockAdminState.blocks, _row)),
                highlight_on_hover=True,
                w="100%",
            ),
            mn.text(EMPTY, fz="13px", c=theme.TEXT_MUTED),
        ),
        _editor(),
        gap=12,
    )


def _start_content() -> rx.Component:
    return mn.stack(
        mn.text(START_LABEL, fz="13px", fw=500),
        rx.match(
            BlockAdminState.chapter_type,
            (
                "table",
                mn.tags_input(
                    value=BlockAdminState.columns,
                    on_change=_set("columns"),
                    placeholder="Spalten, " + ITEMS_HINT,
                ),
            ),
            (
                "stories",
                mn.stack(
                    mn.text(GROUP_LABEL, fz="12px", c=theme.TEXT_MUTED),
                    segmented(
                        BlockAdminState.group_by, _set("group_by"), GROUP_OPTIONS
                    ),
                    gap=4,
                ),
            ),
            (
                "calc",
                mn.multi_select(
                    label=VALUES_LABEL,
                    data=VALUE_OPTIONS,
                    value=BlockAdminState.fields,
                    on_change=_set("fields"),
                    combobox_props={"zIndex": theme.MODAL_Z_INDEX + 1},
                ),
            ),
            rx.box(
                chapter_editor(
                    content=BlockAdminState.content_html,
                    editable=True,
                    on_update=_set("content_html"),
                    float_class_name="aq-admin-editor-row",
                    key=BlockAdminState.editor_nonce.to(str),
                ),
                class_name="aq-admin-editor",
            ),
        ),
        gap=6,
    )


def _form() -> rx.Component:
    return mn.stack(
        mn.group(
            mn.text_input(
                label=KEY_LABEL,
                description=KEY_HINT,
                value=BlockAdminState.key,
                on_change=_set("key"),
                disabled=~BlockAdminState.creating,
                custom_attrs={"maxLength": 50},
                style={"flex": 1},
            ),
            mn.text_input(
                label=TITLE_LABEL,
                value=BlockAdminState.title,
                on_change=_set("title"),
                custom_attrs={"maxLength": 255},
                style={"flex": 2},
            ),
            align="flex-start",
            grow=True,
        ),
        mn.group(
            mn.stack(
                mn.text(TYPE_LABEL, fz="13px", fw=500),
                segmented(
                    BlockAdminState.chapter_type, _set("chapter_type"), TYPE_OPTIONS
                ),
                gap=4,
            ),
            mn.stack(
                mn.text(LEVEL_LABEL, fz="13px", fw=500),
                segmented(BlockAdminState.level, _set("level"), LEVEL_OPTIONS),
                gap=4,
            ),
            align="flex-start",
        ),
        _start_content(),
        mn.textarea(
            label=GUIDE_LABEL,
            value=BlockAdminState.guiding_question,
            on_change=_set("guiding_question"),
            autosize=True,
            min_rows=2,
            custom_attrs={"maxLength": 2000},
        ),
        mn.tags_input(
            label=RULES_LABEL,
            description=ITEMS_HINT,
            value=BlockAdminState.content_rules,
            on_change=_set("content_rules"),
        ),
        mn.textarea(
            label=PROMPT_LABEL,
            description=PROMPT_HINT,
            value=BlockAdminState.prompt_text,
            on_change=_set("prompt_text"),
            autosize=True,
            min_rows=2,
            custom_attrs={"maxLength": 4000},
        ),
        mn.tags_input(
            label=INFO_LABEL,
            description=ITEMS_HINT,
            value=BlockAdminState.required_info,
            on_change=_set("required_info"),
        ),
        mn.multi_select(
            label=CHECKS_LABEL,
            data=CHECK_OPTIONS,
            value=BlockAdminState.checks,
            on_change=_set("checks"),
            combobox_props={"zIndex": theme.MODAL_Z_INDEX + 1},
        ),
        mn.switch(
            label=ACTIVE_LABEL,
            checked=BlockAdminState.active,
            on_change=_set("active"),
        ),
        rx.cond(
            ~BlockAdminState.creating,
            mn.text(
                rx.cond(
                    BlockAdminState.used_in.length() > 0,
                    USED_IN + BlockAdminState.used_in.join(", "),
                    NOT_USED,
                ),
                fz="12px",
                c=theme.TEXT_MUTED,
            ),
        ),
        mn.group(
            rx.cond(
                ~BlockAdminState.creating & (BlockAdminState.used_in.length() == 0),
                mn.button(
                    DELETE,
                    color="red",
                    variant="subtle",
                    on_click=BlockAdminState.delete(BlockAdminState.key),
                ),
            ),
            mn.button(CANCEL, variant="subtle", on_click=BlockAdminState.close_editor),
            mn.button(SAVE, on_click=BlockAdminState.save),
            justify="flex-end",
        ),
        gap=12,
        pb=18,
    )


def _editor() -> rx.Component:
    return mn.modal(
        rx.flex(
            rx.box(_form(), class_name="alloq-modal-scroll"),
            direction="column",
            class_name="alloq-modal-inner",
        ),
        title=EDIT_TITLE,
        opened=BlockAdminState.editor_open,
        on_close=BlockAdminState.close_editor,
        size="xl",
        centered=True,
        class_name=MODAL_CLASS,
        overlay_props=MODAL_OVERLAY,
    )
