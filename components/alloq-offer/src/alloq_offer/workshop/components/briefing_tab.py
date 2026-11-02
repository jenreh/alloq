"""Tab "Briefing": statements by type with their places in the sources."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.list_view import empty_list
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.workshop.states.briefing_state import BriefingState

EMPTY = "Noch kein Briefing. Es entsteht mit dem ersten Entwurf."
CONFIRM = "Als fachliche Entscheidung bestätigen"
WITHDRAW = "Bestätigung zurücknehmen"
CONFIRMED = "Bestätigt"
RECHECK = "Bitte prüfen: ohne Quellenbezug"

Item = ObjectVar[dict[str, Any]]


def _item(item: Item) -> rx.Component:
    return mn.stack(
        mn.group(
            mn.text(item["text"], fz="13px", style={"flex": "1 1 320px"}),
            rx.cond(
                item["confirmed"],
                mn.button(
                    WITHDRAW,
                    variant="subtle",
                    size="compact-xs",
                    on_click=BriefingState.confirm(item["id"], False),
                ),
                mn.button(
                    CONFIRM,
                    variant="default",
                    size="compact-xs",
                    on_click=BriefingState.confirm(item["id"], True),
                ),
            ),
            justify="space-between",
            align="flex-start",
        ),
        mn.group(
            rx.cond(
                item["confirmed"], mn.badge(CONFIRMED, color="green", variant="light")
            ),
            rx.cond(
                item["recheck"], mn.badge(RECHECK, color="yellow", variant="light")
            ),
            rx.foreach(
                item["refs"].to(list[str]),
                lambda ref: mn.badge(ref, variant="outline", color="gray", size="sm"),
            ),
            gap=6,
        ),
        gap=6,
        py=10,
        style={"borderTop": f"1px solid {theme.SEPARATOR}"},
    )


def _group(group: ObjectVar[dict[str, Any]]) -> rx.Component:
    return mn.stack(
        mn.text(group["type"].to(str), fw=650, fz="14px"),
        rx.foreach(group["items"].to(list[dict[str, Any]]), _item),
        gap=0,
        p=16,
        style=theme.CARD,
    )


def briefing_tab() -> rx.Component:
    return mn.box(
        rx.cond(
            BriefingState.is_empty,
            empty_list(EMPTY),
            mn.stack(rx.foreach(BriefingState.groups, _group), gap=12, maw=900),
        ),
        p=20,
    )
