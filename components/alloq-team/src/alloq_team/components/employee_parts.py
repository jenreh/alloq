"""Small display helpers shared by the team list and its inspector."""

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.list_view import tile
from alloq_team.states.team_list_state import TeamDetail
from reflex.vars import ObjectVar

TONE_COLORS = {
    "negative": theme.NEGATIVE,
    "warning": theme.WARNING,
    "positive": theme.POSITIVE,
}


def tone_color(tone: rx.Var[str]) -> rx.Var[str]:
    return rx.match(tone, *TONE_COLORS.items(), theme.TEXT_TERTIARY).to(str)


def employee_avatar(row: ObjectVar[TeamDetail], *, large: bool = False) -> rx.Component:
    return tile(row.initials, row.color, large=large, round_=True)


def load_label(row: ObjectVar[TeamDetail]) -> rx.Var[str]:
    label = rx.cond(row.absent_now, "abwesend", row.load_percent.to(str) + " %")
    return label.to(str)
