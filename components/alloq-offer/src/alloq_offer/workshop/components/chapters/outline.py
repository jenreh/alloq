"""The outline column: frame entries, chapters to drag, "+ Kapitel"."""

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.sortable import sortable_item, sortable_list

import appkit_mantine as mn
from alloq_offer.workshop.components.chapters.blocks import Row
from alloq_offer.workshop.components.chapters.labels import TYPE_SHORT, by_type
from alloq_offer.workshop.states.chapter_state import ChapterState
from alloq_offer.workshop.states.review_state import ReviewState

TITLE = "Gliederung"
ADD = "+ Kapitel"
DRAFT_ALL = "Fehlende Kapitel vorschlagen"
OUTLINE_LABEL = "Gliederung des Angebots"
DRAG_HINT = (
    "Eingabetaste öffnet das Kapitel. Mit der Leertaste aufnehmen, mit den "
    "Pfeiltasten verschieben und mit der Leertaste ablegen; Escape bricht ab."
)
PROTECTED = "Geschützt"
ADD_SUB = "Unterkapitel einfügen"
INDENT = "Einrücken (Unterkapitel)"
OUTDENT = "Ausrücken (Kapitel)"
COLLAPSE = "Unterkapitel ein- oder ausblenden"
STATUS = {
    "blocker": ("Blocker", theme.NEGATIVE),
    "findings": ("Befunde", theme.WARNING),
    "review": ("Bitte prüfen", theme.WARNING),
    "proposal": ("Vorschlag", theme.ACCENT),
}


def _dot(label: str, color: str) -> rx.Component:
    return mn.tooltip(
        rx.el.span(
            class_name="aq-doc-dot",
            style={"background": color},
            aria_label=label,
            role="img",
        ),
        label=label,
        z_index=theme.PAGE_POPOVER_Z_INDEX,
    )


def _status(chapter: Row) -> rx.Component:
    key = chapter["key"].to(str)
    return rx.fragment(
        rx.cond(
            ReviewState.blocker_keys.contains(key),
            _dot(*STATUS["blocker"]),
            rx.cond(ReviewState.other_keys.contains(key), _dot(*STATUS["findings"])),
        ),
        rx.cond(chapter["needs_review"].to(bool), _dot(*STATUS["review"])),
        rx.cond(chapter["proposal"].to(bool), _dot(*STATUS["proposal"])),
        rx.cond(
            chapter["protected"].to(bool),
            mn.tooltip(
                rx.icon("lock", size=12, color=theme.TEXT_MUTED, aria_label=PROTECTED),
                label=PROTECTED,
                z_index=theme.PAGE_POPOVER_Z_INDEX,
            ),
        ),
    )


def _action(icon: str, label: str, event: rx.EventSpec) -> rx.Component:
    return mn.tooltip(
        mn.action_icon(
            rx.icon(icon, size=13),
            variant="subtle",
            color="gray",
            size="sm",
            aria_label=label,
            on_click=event.stop_propagation,
        ),
        label=label,
        z_index=theme.PAGE_POPOVER_Z_INDEX,
    )


def _actions(chapter: Row) -> rx.Component:
    """Hover actions of a row: sub chapter, indent, outdent."""
    key = chapter["key"].to(str)
    main = chapter["main"].to(bool)
    return rx.el.span(
        rx.cond(
            main,
            _action("plus", ADD_SUB, ChapterState.add_subchapter(key)),
        ),
        rx.cond(
            main & ~chapter["first"].to(bool),
            _action("indent-increase", INDENT, ChapterState.indent_chapter(key)),
        ),
        rx.cond(
            ~main & ~chapter["attached"].to(bool),
            _action("indent-decrease", OUTDENT, ChapterState.outdent_chapter(key)),
        ),
        class_name="aq-doc-row-actions",
    )


def _chevron(chapter: Row) -> rx.Component:
    key = chapter["key"].to(str)
    return rx.cond(
        chapter["has_children"].to(bool),
        rx.el.button(
            rx.icon("chevron-down", size=13),
            type="button",
            class_name="aq-doc-chevron",
            aria_label=COLLAPSE,
            custom_attrs={
                "aria-expanded": rx.cond(
                    ChapterState.collapsed.contains(key), "false", "true"
                )
            },
            on_click=ChapterState.toggle_collapse(key).stop_propagation,
        ),
        rx.el.span(class_name="aq-doc-chevron-space"),
    )


def _row(chapter: Row) -> rx.Component:
    key = chapter["key"].to(str)
    return rx.el.div(
        rx.el.span(rx.icon("grip-vertical", size=14), class_name="aq-doc-grip"),
        _chevron(chapter),
        rx.el.span(chapter["label"].to(str), class_name="aq-doc-row-title"),
        _status(chapter),
        _actions(chapter),
        rx.el.span(by_type(chapter["type"], TYPE_SHORT), class_name="aq-doc-type"),
        class_name="aq-doc-row",
        custom_attrs={
            "data-active": rx.cond(ChapterState.active_key == key, "true", "false"),
            "aria-current": rx.cond(ChapterState.active_key == key, "true", "false"),
            "data-level": chapter["level"].to(str),
            "data-main": rx.cond(chapter["main"].to(bool), "true", "false"),
            "data-attached": rx.cond(chapter["attached"].to(bool), "true", "false"),
            "data-hidden": rx.cond(chapter["hidden"].to(bool), "true", "false"),
        },
        on_click=ChapterState.jump_to(key),
    )


def _frame(title: rx.Var[str]) -> rx.Component:
    return rx.el.div(title, class_name="aq-doc-frame-entry")


def outline() -> rx.Component:
    return rx.el.nav(
        rx.el.div(
            mn.text(TITLE, fz="11.5px", fw=600, c=theme.TEXT_MUTED),
            mn.button(
                ADD,
                variant="subtle",
                size="compact-sm",
                on_click=ChapterState.open_add,
            ),
            class_name="aq-doc-outline-head",
        ),
        rx.foreach(ChapterState.frame_before, _frame),
        sortable_list(
            rx.foreach(
                ChapterState.outline_rows,
                lambda chapter, index: sortable_item(
                    _row(chapter),
                    item_id=chapter["key"].to(str),
                    index=index,
                    disabled=chapter["protected"].to(bool),
                    class_name="aq-doc-sortable-item",
                ),
            ),
            ids=ChapterState.chapter_ids,
            version=ChapterState.order_version,
            droppable_id="chapters",
            instructions=DRAG_HINT,
            on_reorder=ChapterState.reorder,
        ),
        rx.foreach(ChapterState.frame_after, _frame),
        mn.button(
            DRAFT_ALL,
            variant="default",
            size="xs",
            mt=12,
            loading=ChapterState.drafting,
            on_click=ChapterState.draft_all,
        ),
        class_name="aq-doc-outline",
        aria_label=OUTLINE_LABEL,
    )
