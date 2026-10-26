"""Tab "Kapitel": the offer as one document with outline and chapter panel."""

import reflex as rx

from alloq_offer.workshop.components.chapters.dialogs import (
    add_dialog,
    instruction_dialog,
    remove_dialog,
)
from alloq_offer.workshop.components.chapters.document import document
from alloq_offer.workshop.components.chapters.outline import outline
from alloq_offer.workshop.components.chapters.panel import panel
from alloq_offer.workshop.states.chapter_state import ChapterState

POLL_MS = 3000


def chapters_tab() -> rx.Component:
    return rx.box(
        outline(),
        document(),
        panel(),
        add_dialog(),
        remove_dialog(),
        instruction_dialog(),
        rx.cond(
            ChapterState.drafting,
            rx.moment(
                interval=POLL_MS,
                on_change=ChapterState.refresh_drafts,
                display="none",
            ),
        ),
        class_name="aq-split",
    )
