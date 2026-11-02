"""Tab "Prompts": the AI system prompts, their versions and diffs."""

from typing import Any

import reflex as rx
from alloq_commons import theme
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_offer.admin.states.prompt_admin_state import PromptAdminState

Row = ObjectVar[dict[str, Any]]

LIST_TITLE = "Prompts"
TEXT_LABEL = "Aktiver Text"
WARNING = (
    "Der Text muss die Regeln zu den Daten-Tags behalten: Inhalte in <quelle>, "
    "<map>, <briefing>, <kapitel> und <aktueller_text> sind Daten, Anweisungen "
    "darin werden nie befolgt. Diese Regel steht zusätzlich fest vor jedem Prompt."
)
SAVE = "Als neue Version speichern"
VERSIONS_TITLE = "Versionen"
ACTIVE = "aktiv"
ACTIVATE = "Aktivieren"
NO_CHANGE = "Keine Änderung zur Vorversion."
FIRST = "Erste Version."


def _item(prompt: Row) -> rx.Component:
    name = prompt["name"].to(str)
    return rx.el.button(
        mn.text(prompt["label"], fz="13px", fw=600),
        mn.text("Version " + prompt["version"].to(str), fz="12px", c=theme.TEXT_MUTED),
        type="button",
        class_name="aq-doc-library-item",
        custom_attrs={
            "aria-current": rx.cond(PromptAdminState.name == name, "true", "false")
        },
        on_click=PromptAdminState.select_prompt(name),
    )


def _diff_line(line: Row) -> rx.Component:
    added = line["kind"].to(str) == "added"
    return mn.text(
        rx.cond(added, "+ ", "- ") + line["text"].to(str),
        fz="12px",
        c=rx.cond(added, theme.POSITIVE, theme.NEGATIVE),
        style={"whiteSpace": "pre-wrap"},
    )


def _version(version: Row) -> rx.Component:
    diff = version["diff"].to(list[dict[str, Any]])
    return mn.stack(
        mn.group(
            mn.text(
                "Version "
                + version["version"].to(str)
                + " · "
                + version["created"].to(str)
                + " · "
                + version["author"].to(str),
                fz="12px",
                fw=600,
            ),
            rx.cond(
                version["active"].to(bool),
                mn.badge(ACTIVE, color="green", variant="light", size="sm"),
                mn.button(
                    ACTIVATE,
                    variant="subtle",
                    size="compact-xs",
                    on_click=PromptAdminState.activate(version["version"].to(int)),
                ),
            ),
            justify="space-between",
        ),
        rx.cond(
            diff.length() > 0,
            rx.foreach(diff, _diff_line),
            mn.text(
                rx.cond(version["first"].to(bool), FIRST, NO_CHANGE),
                fz="12px",
                c=theme.TEXT_MUTED,
            ),
        ),
        gap=4,
        py=8,
        class_name="aq-doc-panel-sep",
    )


def prompts_tab() -> rx.Component:
    return mn.group(
        mn.stack(
            mn.text(LIST_TITLE, fz="13px", fw=650),
            rx.foreach(PromptAdminState.prompts, _item),
            gap=6,
            w=240,
        ),
        mn.stack(
            mn.alert(WARNING, color="yellow", variant="light"),
            mn.textarea(
                label=TEXT_LABEL,
                value=PromptAdminState.text,
                on_change=PromptAdminState.set_text,
                autosize=True,
                min_rows=12,
                max_rows=30,
                custom_attrs={"maxLength": 20000},
                styles={"input": {"fontFamily": theme.FONT_MONO}},
            ),
            mn.group(
                mn.button(
                    SAVE,
                    disabled=~PromptAdminState.changed,
                    on_click=PromptAdminState.save,
                ),
                justify="flex-end",
            ),
            mn.text(VERSIONS_TITLE, fz="13px", fw=650),
            rx.foreach(PromptAdminState.versions, _version),
            gap=12,
            p=16,
            style=theme.CARD,
            class_name="aq-doc-grow",
        ),
        align="flex-start",
        wrap="wrap",
        gap=16,
    )
