"""Small display helpers shared by the project list and its inspector."""

import reflex as rx
from alloq_commons.components.formatters import format_date_de
from alloq_commons.components.list_view import tile
from alloq_commons.models.project import Project
from alloq_project.states.project_list_state import STATUS_TONES
from reflex.vars import ObjectVar


def status_tone(state: rx.Var[str]) -> rx.Var[str]:
    return rx.match(state, *STATUS_TONES.items(), "neutral").to(str)


def project_tile(project: ObjectVar[Project], *, large: bool = False) -> rx.Component:
    text = rx.cond(project.name_de != "", project.name_de, project.code).to(str)
    return tile(text[:2].upper(), project.color, large=large)


def period(project: ObjectVar[Project]) -> rx.Var[str]:
    start = rx.cond(project.start_date, format_date_de(project.start_date), "—")
    end = rx.cond(project.end_date, format_date_de(project.end_date), "—")
    return (start.to(str) + " – " + end.to(str)).to(str)
