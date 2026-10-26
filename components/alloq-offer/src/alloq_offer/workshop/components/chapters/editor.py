"""The text editor of the selected chapter and the floating module toolbar."""

from typing import Any

import reflex as rx
from reflex.components.component import NoSSRComponent
from reflex.event import EventHandler
from reflex.vars.base import Var

import appkit_mantine as mn
from appkit_mantine.base import MANTINE_VERSION
from appkit_mantine.tiptap import TIPTAP_VERSION

CONTROL_GROUPS = [["bold", "italic"], ["h3", "h4"], ["bulletList", "orderedList"]]
HISTORY_CONTROLS = [["undo", "redo"]]
EDITOR_LABELS = {
    "boldControlLabel": "Fett",
    "italicControlLabel": "Kursiv",
    "h3ControlLabel": "Zwischenüberschrift",
    "h4ControlLabel": "Kleine Zwischenüberschrift",
    "bulletListControlLabel": "Aufzählung",
    "orderedListControlLabel": "Nummerierte Liste",
    "undoControlLabel": "Rückgängig",
    "redoControlLabel": "Wiederholen",
}
TOOLBAR_CLASS = "aq-doc-toolbar"
TOOLBAR_LABEL = "Werkzeuge für das Kapitel"
PROSE_CLASS = "aq-doc-prose"


class ChapterEditor(NoSSRComponent):
    """Tiptap with Mantine; the children join the controls in the toolbar card."""

    library = rx.asset("chapter_editor.jsx", shared=True).importable_path
    tag = "ChapterEditor"
    lib_dependencies: list[str] = [
        f"@mantine/tiptap@{MANTINE_VERSION}",
        f"@tiptap/react@{TIPTAP_VERSION}",
        f"@tiptap/pm@{TIPTAP_VERSION}",
        f"@tiptap/starter-kit@{TIPTAP_VERSION}",
    ]

    content: Var[str]
    editable: Var[bool]
    control_groups: Var[list[list[str]]]
    toolbar_class_name: Var[str]
    toolbar_label: Var[str]
    content_class_name: Var[str]
    labels: Var[dict[str, str]]
    header: Var[rx.Component]
    """Shown above the text, below the toolbar row (the chapter title)."""

    on_update: EventHandler[lambda html: [html]]

    on_blur: EventHandler[lambda html: [html]]
    """When the editor loses the focus, with its text: the save is not delayed."""

    def add_imports(self) -> dict[str, list[str]]:
        return {
            "react": ["lazy"],
            f"$/{rx.constants.Dirs.UTILS}/context": ["ClientSide"],
        }


def chapter_editor(*toolbar: rx.Component, **props: Any) -> rx.Component:
    return ChapterEditor.create(
        *toolbar,
        control_groups=CONTROL_GROUPS + HISTORY_CONTROLS,
        toolbar_class_name=TOOLBAR_CLASS,
        toolbar_label=TOOLBAR_LABEL,
        content_class_name=PROSE_CLASS,
        labels=EDITOR_LABELS,
        **props,
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
