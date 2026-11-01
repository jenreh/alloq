"""The optional description below an image or table chapter (no heading)."""

import reflex as rx

from alloq_offer.workshop.components.chapters.blocks import Row
from alloq_offer.workshop.states.chapter_state import ChapterState

CAPTION_LABEL = "Beschreibung"
CAPTION_PLACEHOLDER = "Beschreibung hinzufügen (freiwillig)"


def view(chapter: Row) -> rx.Component:
    text = chapter["description"].to(str)
    return rx.cond(text != "", rx.el.p(text, class_name="aq-doc-caption"))


def editing(chapter: Row) -> rx.Component:
    """Uncontrolled, keyed by the stored text: a failed save shows it again."""
    text = chapter["description"].to(str)
    return rx.el.input(
        default_value=text,
        key=chapter["key"].to(str)
        + ":"
        + text
        + ":"
        + ChapterState.input_reset.to_string(),
        placeholder=CAPTION_PLACEHOLDER,
        aria_label=CAPTION_LABEL,
        read_only=ChapterState.chapter_locked,
        custom_attrs={"maxLength": 500},
        class_name="aq-doc-caption aq-doc-caption-input",
        on_blur=ChapterState.set_caption,
    )
