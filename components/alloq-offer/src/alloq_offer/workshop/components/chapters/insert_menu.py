"""The "+" in the gap between two chapters (Confluence): insert a chapter there."""

import reflex as rx
from alloq_commons import theme

import appkit_mantine as mn
from alloq_offer.workshop.states.chapter_state import ChapterState

INSERT_LABEL = "Kapitel hier einfügen"
NEEDS_PARENT_HINT = "Tabellen und Bilder stehen unter einem Kapitel."
# (kind, label, icon); "sub" and "library" are no chapter types.
CHOICES = [
    ("prose", "Text", "text"),
    ("sub", "Unterkapitel", "indent-increase"),
    ("table", "Tabelle", "table"),
    ("image", "Bild", "image"),
    ("stories", "User Stories", "list-checks"),
    ("calc", "Kalkulation", "calculator"),
    ("library", "Aus Bibliothek …", "library"),
]
# Need a chapter before the gap.
AFTER_ONLY = {"sub", "table", "image"}


def insert_gap(after_key: rx.Var[str] | str) -> rx.Component:
    """A thin line with a "+" left of it; ``after_key`` "" is the top gap."""
    at_start = after_key == ""
    items = [
        mn.menu.item(
            label,
            left_section=rx.icon(icon, size=14),
            disabled=at_start if kind in AFTER_ONLY else False,
            on_click=ChapterState.insert_chapter(after_key, kind),
        )
        for kind, label, icon in CHOICES
    ]
    return rx.el.div(
        mn.menu(
            mn.menu.target(
                rx.el.button(
                    rx.icon("plus", size=14),
                    type="button",
                    class_name="aq-doc-gap-button",
                    aria_label=INSERT_LABEL,
                    title=INSERT_LABEL,
                )
            ),
            mn.menu.dropdown(
                *items,
                rx.cond(
                    at_start,
                    mn.menu.label(NEEDS_PARENT_HINT),
                ),
            ),
            position="bottom-start",
            shadow="md",
            z_index=theme.PAGE_POPOVER_Z_INDEX,
        ),
        rx.el.span(class_name="aq-doc-gap-line"),
        class_name="aq-doc-gap",
        on_click=rx.stop_propagation,
    )
