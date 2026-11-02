"""The text editors of the page, the one formatting toolbar and the module toolbar."""

from typing import Any

import reflex as rx
from reflex.components.component import NoSSRComponent
from reflex.event import EventHandler, no_args_event_spec
from reflex.vars.base import Var

import appkit_mantine as mn
from alloq_offer.workshop.content.schema import MAX_COLUMNS, TEXT_COLORS
from appkit_mantine.base import MANTINE_VERSION
from appkit_mantine.tiptap import TIPTAP_VERSION

EDITOR_LABELS = {
    "boldControlLabel": "Fett",
    "italicControlLabel": "Kursiv",
    "underlineControlLabel": "Unterstrichen",
    "strikeControlLabel": "Durchgestrichen",
    "clearFormattingControlLabel": "Formatierung entfernen",
    "codeControlLabel": "Code im Text",
    "codeBlockControlLabel": "Codeblock",
    "subscriptControlLabel": "Tiefgestellt",
    "superscriptControlLabel": "Hochgestellt",
    "h3ControlLabel": "Zwischenüberschrift",
    "h4ControlLabel": "Kleine Zwischenüberschrift",
    "blockquoteControlLabel": "Zitat",
    "bulletListControlLabel": "Aufzählung",
    "orderedListControlLabel": "Nummerierte Liste",
    "tasksControlLabel": "Aufgabenliste",
    "alignLeftControlLabel": "Linksbündig",
    "alignCenterControlLabel": "Zentriert",
    "alignRightControlLabel": "Rechtsbündig",
    "alignJustifyControlLabel": "Blocksatz",
    "linkControlLabel": "Link einfügen",
    "unlinkControlLabel": "Link entfernen",
    "linkEditorInputLabel": "Adresse des Links",
    "linkEditorInputPlaceholder": "https://…",
    "linkEditorExternalLink": "In neuem Fenster öffnen",
    "linkEditorInternalLink": "Im selben Fenster öffnen",
    "linkEditorSave": "Speichern",
    "colorPickerControlLabel": "Textfarbe",
    "colorPickerCancel": "Abbrechen",
    "colorPickerClear": "Farbe entfernen",
    "colorPickerColorPicker": "Farbwähler",
    "colorPickerPalette": "Farben",
    "colorPickerSave": "Speichern",
    "unsetColorControlLabel": "Farbe entfernen",
    "highlightControlLabel": "Markieren",
    "hrControlLabel": "Trennlinie",
    "undoControlLabel": "Rückgängig",
    "redoControlLabel": "Wiederholen",
}
GUTTER_LABELS = {
    "add": "Block darunter einfügen",
    "grip": "Ziehen zum Verschieben, klicken für Aktionen",
    "insertMenu": "Art des neuen Blocks",
    "actionsMenu": "Aktionen für den Block",
    "duplicate": "Duplizieren",
    "remove": "Löschen",
    "convert": "Umwandeln in",
    "paragraph": "Absatz",
    "heading3": "Zwischenüberschrift",
    "heading4": "Kleine Zwischenüberschrift",
    "bulletList": "Aufzählung",
    "orderedList": "Nummerierte Liste",
    "taskList": "Aufgabenliste",
    "blockquote": "Zitat",
    "codeBlock": "Codeblock",
}
PLACEHOLDER = "Text schreiben …"
INDENT_LABEL = "Listenpunkt einrücken"
MORE_LABEL = "Weitere Werkzeuge"
OUTDENT_LABEL = "Listenpunkt ausrücken"
TOOLBAR_CLASS = "aq-doc-toolbar"
TOOLBAR_LABEL = "Werkzeuge für das Kapitel"
FORMAT_TOOLBAR_LABEL = "Formatierung"
PROSE_CLASS = "aq-doc-prose"
LIBRARY = rx.asset("chapter_editor.jsx", shared=True).importable_path
TABLE_LIBRARY = rx.asset("table_editor.jsx", shared=True).importable_path
IMAGE_LIBRARY = rx.asset("image_editor.jsx", shared=True).importable_path
# Imported by chapter_editor.jsx; shared assets must come from this module.
rx.asset("block_gutter.jsx", shared=True)
DEPENDENCIES = [
    f"@mantine/tiptap@{MANTINE_VERSION}",
    f"@tiptap/react@{TIPTAP_VERSION}",
    f"@tiptap/pm@{TIPTAP_VERSION}",
    f"@tiptap/starter-kit@{TIPTAP_VERSION}",
    f"@tiptap/extension-blockquote@{TIPTAP_VERSION}",
    f"@tiptap/extension-highlight@{TIPTAP_VERSION}",
    f"@tiptap/extension-subscript@{TIPTAP_VERSION}",
    f"@tiptap/extension-superscript@{TIPTAP_VERSION}",
    f"@tiptap/extension-text-align@{TIPTAP_VERSION}",
    f"@tiptap/extension-text-style@{TIPTAP_VERSION}",
    f"@tiptap/extension-list@{TIPTAP_VERSION}",
    f"@tiptap/extensions@{TIPTAP_VERSION}",
    f"@tiptap/extension-document@{TIPTAP_VERSION}",
    f"@tiptap/extension-table@{TIPTAP_VERSION}",
]
TABLE_LABELS = {
    **EDITOR_LABELS,
    "tableRowBeforeControlLabel": "Zeile darüber einfügen",
    "tableRowAfterControlLabel": "Zeile darunter einfügen",
    "tableRowDeleteControlLabel": "Zeile löschen",
    "tableColumnBeforeControlLabel": "Spalte links einfügen",
    "tableColumnAfterControlLabel": "Spalte rechts einfügen",
    "tableColumnDeleteControlLabel": "Spalte löschen",
    "tableToolbarLabel": "Werkzeuge für die Tabelle",
    "tableRemoveLabel": "Tabelle löschen",
    "selectRowLabel": "Zeile auswählen",
    "selectColumnLabel": "Spalte auswählen",
    "addRowLabel": "Zeile hier einfügen",
    "addColumnLabel": "Spalte hier einfügen",
}


class _Lazy(NoSSRComponent):
    library = LIBRARY
    lib_dependencies: list[str] = DEPENDENCIES

    def add_imports(self) -> dict[str, list[str]]:
        return {
            "react": ["lazy"],
            f"$/{rx.constants.Dirs.UTILS}/context": ["ClientSide"],
        }


class ChapterEditor(_Lazy):
    """The text of one chapter, editable in place; mounts near the viewport."""

    tag = "ChapterEditor"

    content: Var[str]
    editable: Var[bool]
    placeholder: Var[str]
    gutter_labels: Var[dict[str, str]]
    content_class_name: Var[str]
    header: Var[rx.Component]
    """Shown above the text (the chapter title)."""

    on_update: EventHandler[lambda html: [html]]

    on_blur: EventHandler[lambda html: [html]]
    """When the editor loses the focus, with its text: the save is not delayed."""

    on_focus: EventHandler[no_args_event_spec]
    """The chapter becomes the selected one."""


class ChapterToolbar(_Lazy):
    """The one formatting toolbar; acts on the text chapter focused last."""

    tag = "ChapterToolbar"

    labels: Var[dict[str, str]]
    colors: Var[list[str]]
    toolbar_label: Var[str]
    more_label: Var[str]
    indent_label: Var[str]
    outdent_label: Var[str]


class TableEditor(_Lazy):
    """The grid of a table chapter, edited like a Confluence table."""

    library = TABLE_LIBRARY
    tag = "TableEditor"

    content: Var[str]
    editable: Var[bool]
    labels: Var[dict[str, str]]
    max_columns: Var[int]
    content_class_name: Var[str]

    on_update: EventHandler[lambda html: [html]]
    on_blur: EventHandler[lambda html: [html]]
    on_focus: EventHandler[no_args_event_spec]
    on_remove: EventHandler[no_args_event_spec]
    """"Tabelle löschen" in the table toolbar: the chapter's remove flow."""


def table_editor(*children: rx.Component, **props: Any) -> rx.Component:
    return TableEditor.create(
        *children,
        labels=TABLE_LABELS,
        max_columns=MAX_COLUMNS,
        content_class_name=PROSE_CLASS,
        **props,
    )


IMAGE_LABELS = {
    "toolbar": "Werkzeuge für das Bild",
    "select": "Bild auswählen",
    "left": "Links ausrichten",
    "center": "Zentrieren",
    "right": "Rechts ausrichten",
    "remove": "Bild löschen",
}


class ImageFrame(NoSSRComponent):
    """The picture of an image chapter with its Confluence toolbar."""

    library = IMAGE_LIBRARY
    tag = "ImageFrame"
    lib_dependencies: list[str] = []

    src: Var[str]
    alt: Var[str]
    width: Var[int]
    align: Var[str]
    editable: Var[bool]
    sizes: Var[list[dict[str, str]]]
    labels: Var[dict[str, str]]

    on_resize: EventHandler[lambda width: [width]]
    on_align: EventHandler[lambda align: [align]]
    on_remove: EventHandler[no_args_event_spec]

    def add_imports(self) -> dict[str, list[str]]:
        return {
            "react": ["lazy"],
            f"$/{rx.constants.Dirs.UTILS}/context": ["ClientSide"],
        }


def image_frame(*children: rx.Component, **props: Any) -> rx.Component:
    return ImageFrame.create(*children, labels=IMAGE_LABELS, **props)


def chapter_editor(**props: Any) -> rx.Component:
    return ChapterEditor.create(
        placeholder=PLACEHOLDER,
        gutter_labels=GUTTER_LABELS,
        content_class_name=PROSE_CLASS,
        **props,
    )


def chapter_toolbar(*children: rx.Component) -> rx.Component:
    return ChapterToolbar.create(
        *children,
        labels=EDITOR_LABELS,
        colors=list(TEXT_COLORS.values()),
        class_name="aq-doc-format-bar",
        toolbar_label=FORMAT_TOOLBAR_LABEL,
        more_label=MORE_LABEL,
        indent_label=INDENT_LABEL,
        outdent_label=OUTDENT_LABEL,
    )


def floating_toolbar(*children: rx.Component) -> rx.Component:
    """The toolbar card over the top edge of the selected block."""
    return rx.el.div(
        rx.el.div(
            *children,
            class_name=TOOLBAR_CLASS,
            role="toolbar",
            aria_label=TOOLBAR_LABEL,
        ),
        class_name="aq-doc-float",
    )


def toolbar_separator() -> rx.Component:
    return rx.el.span(class_name="aq-doc-toolbar-sep")


def tool_button(label: Any, **props: Any) -> rx.Component:
    """A text button in the toolbar card."""
    return mn.button(label, variant="subtle", color="gray", size="compact-sm", **props)
