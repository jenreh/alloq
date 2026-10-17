"""Absence timeline: day-precise bars, week coverage and upcoming absences."""

import reflex as rx
from alloq_commons.components.dialogs import delete_dialog
from alloq_project.components.planning_shared import (
    GRID_WRAPPER_STYLE,
    MONTH_START_BORDER,
)
from alloq_project.services.planning_gantt import (
    DAYS_PER_WEEK,
    GANTT_BAR_PX,
    GANTT_LANE_PX,
    GANTT_PADDING_PX,
)
from alloq_project.states.planning_absence_state import PlanningAbsenceState
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_project.states.planning_models import (
    WEEK_COL_PX,
    AbsenceGanttBar,
    AbsenceGanttRow,
    AffectedProject,
    GanttMark,
    GanttWeek,
    MonthSpan,
    UpcomingAbsence,
)
from alloq_team.components.employee import absence_modal
from alloq_team.states.team_state import TeamState
from reflex.vars import NumberVar, ObjectVar

import appkit_mantine as mn

GANTT = PlanningStore.absence_gantt
LABEL_PX = 232
SUM_PX = 96
WEEK_PX = f"{WEEK_COL_PX}px"
DAY_PX = WEEK_COL_PX / DAYS_PER_WEEK

BAR_BG = "var(--mantine-color-blue-6)"
SELECTED_RING = "0 0 0 2px var(--aq-surface), 0 0 0 4px var(--aq-accent)"
WEEKEND_BG = "light-dark(rgba(0, 0, 0, 0.025), rgba(255, 255, 255, 0.03))"
HOLIDAY_HATCH = (
    "repeating-linear-gradient(135deg, "
    "light-dark(rgba(135, 88, 0, 0.28), rgba(227, 174, 82, 0.35)) 0 2px, "
    "transparent 2px 4px)"
)
# Week line on the left edge of each week, like the week header cells.
LANE_BG = (
    "repeating-linear-gradient(to right, "
    "var(--aq-separator) 0 1px, "
    f"transparent 1px {5 * DAY_PX:.3f}px, "
    f"{WEEKEND_BG} {5 * DAY_PX:.3f}px {WEEK_COL_PX}px)"
)
ROW_LINE = "1px solid var(--alloq-border)"
NUMERIC = {"fontVariantNumeric": "tabular-nums", "whiteSpace": "nowrap"}
HINT = (
    "In einer Zeile ziehen, um eine Abwesenheit einzutragen. "
    "Klick auf einen Balken zeigt die Details."
)


class _AbsenceLane(rx.Component):
    """Timeline lane of one employee; dragging selects a range of days."""

    library = rx.asset("absence_lane.jsx", shared=True).importable_path
    tag = "AbsenceLane"

    day_px: rx.Var[float]
    days: rx.Var[int]
    min_day: rx.Var[int]
    start_iso: rx.Var[str]
    holidays: rx.Var[list[int]]
    on_select_range: rx.EventHandler[lambda start, end: [start, end]]


def _px(value: NumberVar | rx.Var) -> rx.Var[str]:
    return value.to_string() + "px"


def _columns() -> rx.Var[str]:
    return f"{LABEL_PX}px " + _px(GANTT.width_px) + f" {SUM_PX}px"


def _total_width() -> rx.Var[str]:
    return _px(GANTT.width_px + LABEL_PX + SUM_PX)


def _grid_row(*children: rx.Component, style: dict | None = None) -> rx.Component:
    return mn.box(
        *children,
        style={
            "display": "grid",
            "gridTemplateColumns": _columns(),
            "width": _total_width(),
            **(style or {}),
        },
    )


def _sticky(side: str, background: str, **extra: str) -> dict:
    border = "borderRight" if side == "left" else "borderLeft"
    return {
        "position": "sticky",
        side: "0",
        "zIndex": "3",
        "backgroundColor": background,
        border: MONTH_START_BORDER,
        **extra,
    }


# === Header ===


def _month(month: ObjectVar[MonthSpan], index: NumberVar) -> rx.Component:
    return mn.box(
        mn.text(month.label, fz="12px", fw="650", truncate=True),
        style={
            "width": _px(month.span * WEEK_COL_PX),
            "boxSizing": "border-box",
            "display": "flex",
            "alignItems": "center",
            "padding": "0 10px",
            "borderLeft": rx.cond(index > 0, MONTH_START_BORDER, "none"),
        },
    )


def _week(week: ObjectVar[GanttWeek]) -> rx.Component:
    return mn.box(
        mn.text(
            "KW ",
            week.kw,
            fz="11px",
            fw="650",
            c=rx.cond(week.is_current, "var(--aq-warning)", "var(--aq-text)"),
            style=NUMERIC,
        ),
        mn.group(
            mn.text(week.label, fz="10.5px", c="var(--aq-text-muted)", style=NUMERIC),
            rx.cond(
                week.has_holiday,
                mn.box(w=5, h=5, bg="var(--aq-warning)", style={"borderRadius": "50%"}),
            ),
            gap=3,
            wrap="nowrap",
        ),
        custom_attrs={"title": week.title},
        style={
            "width": WEEK_PX,
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "center",
            "gap": "1px",
            "boxSizing": "border-box",
            "borderLeft": rx.cond(
                week.is_month_start, MONTH_START_BORDER, "1px solid var(--aq-separator)"
            ),
            "backgroundColor": rx.cond(week.is_current, "var(--aq-now)", "transparent"),
        },
    )


def _header_label(title: str, hint: rx.Var | str = "") -> rx.Component:
    return mn.box(
        mn.text(title, fz="12.5px", fw="650"),
        mn.text(hint, fz="11px", c="var(--aq-text-muted)") if hint else rx.fragment(),
        style={
            **_sticky("left", "var(--aq-surface-muted)"),
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "center",
            "padding": "0 16px",
        },
    )


def _header_sum(text: str = "") -> rx.Component:
    return mn.box(
        mn.text(text, fz="11.5px", c="var(--aq-text-muted)", ta="right"),
        style={
            **_sticky("right", "var(--aq-surface-muted)"),
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "flex-end",
            "padding": "0 16px",
        },
    )


def _header() -> rx.Component:
    line = "2px solid var(--alloq-border-strong)"
    return mn.box(
        _grid_row(
            _header_label("Mitarbeiter"),
            mn.box(rx.foreach(PlanningStore.month_spans, _month), display="flex"),
            _header_sum("Summe"),
            style={"height": "28px", "borderBottom": ROW_LINE},
        ),
        _grid_row(
            _header_label(GANTT.team_size.to_string() + " Personen"),
            mn.box(rx.foreach(GANTT.weeks, _week), display="flex"),
            _header_sum("Arbeitstage"),
            style={"height": "36px", "borderBottom": line},
        ),
        style={
            "position": "sticky",
            "top": "0",
            "zIndex": "30",
            "backgroundColor": "var(--aq-surface-muted)",
            "width": _total_width(),
        },
    )


# === Body ===


def _week_column(week: ObjectVar[GanttWeek]) -> rx.Component:
    """Current-week tint behind the rows."""
    return mn.box(
        style={
            "width": WEEK_PX,
            "flexShrink": "0",
            "boxSizing": "border-box",
            "backgroundColor": rx.cond(week.is_current, "var(--aq-now)", "transparent"),
        },
    )


def _holiday(mark: ObjectVar[GanttMark]) -> rx.Component:
    return mn.box(
        custom_attrs={"title": mark.title},
        style={
            "position": "absolute",
            "top": "0",
            "bottom": "0",
            "left": _px(mark.left_px),
            "width": f"{DAY_PX:.3f}px",
            "backgroundImage": HOLIDAY_HATCH,
        },
    )


def _overlay() -> rx.Component:
    """Week tints, holidays and today line behind the bars."""
    return mn.box(
        mn.box(
            rx.foreach(GANTT.weeks, _week_column),
            style={"display": "flex", "position": "absolute", "inset": "0"},
        ),
        rx.foreach(GANTT.holidays, _holiday),
        rx.cond(
            GANTT.today_px >= 0,
            mn.box(
                custom_attrs={"title": "Heute"},
                style={
                    "position": "absolute",
                    "top": "0",
                    "bottom": "0",
                    "left": _px(GANTT.today_px),
                    "width": "2px",
                    "marginLeft": "-1px",
                    "backgroundColor": "var(--aq-negative)",
                },
            ),
        ),
        custom_attrs={"aria-hidden": "true"},
        style={
            "position": "absolute",
            "top": "0",
            "bottom": "0",
            "left": f"{LABEL_PX}px",
            "width": _px(GANTT.width_px),
            "pointerEvents": "none",
            "zIndex": "0",
        },
    )


def _stat(value: rx.Var, label: str) -> rx.Component:
    return mn.stack(
        mn.text(value, fz="18px", fw="700", lh="1.2", style=NUMERIC),
        mn.text(label, fz="11px", c="var(--aq-text-muted)"),
        gap=0,
        px=10,
        py=8,
        bg="var(--aq-surface)",
        style={"borderRadius": "8px", "flex": "1"},
    )


def _bar_details(
    row: ObjectVar[AbsenceGanttRow], bar: ObjectVar[AbsenceGanttBar]
) -> rx.Component:
    return mn.stack(
        mn.group(
            mn.stack(
                mn.text(row.name, fz="14px", fw="650"),
                mn.text(
                    bar.period, fz="12.5px", c="var(--aq-text-muted)", style=NUMERIC
                ),
                gap=2,
            ),
            delete_dialog(
                "Abwesenheit löschen",
                f"die Abwesenheit von {row.name} ({bar.period})",
                PlanningAbsenceState.delete_absence(bar.absence_id),  # ty: ignore[invalid-argument-type]
                icon_button=True,
                variant="subtle",
                color="red",
                size="md",
                custom_attrs={"aria-label": "Abwesenheit löschen"},
            ),
            justify="space-between",
            align="flex-start",
            wrap="nowrap",
        ),
        mn.group(
            _stat(bar.work_days, "Arbeitstage"),
            _stat(bar.calendar_days, "Kalendertage"),
            gap=8,
            grow=True,
        ),
        rx.cond(
            bar.holidays_note != "",
            mn.text(bar.holidays_note, fz="12px", c="var(--aq-text-muted)"),
        ),
        rx.cond(
            bar.overlap_note != "",
            mn.group(
                rx.icon("triangle-alert", size=15, style={"flexShrink": "0"}),
                mn.text(bar.overlap_note, fz="12px", lh="1.4"),
                gap=8,
                wrap="nowrap",
                align="flex-start",
                px=10,
                py=8,
                c="var(--aq-negative)",
                bg="var(--aq-negative-soft)",
                style={"borderRadius": "8px"},
            ),
        ),
        gap=10,
    )


def _bar(
    row: ObjectVar[AbsenceGanttRow], bar: ObjectVar[AbsenceGanttBar]
) -> rx.Component:
    top = _px(bar.lane * GANTT_LANE_PX + GANTT_PADDING_PX)
    return rx.fragment(
        mn.popover(
            mn.popover.target(
                # A plain button: Mantine's button base would reset the fill.
                rx.el.button(
                    rx.cond(bar.inside, bar.label, ""),
                    type="button",
                    aria_label=bar.aria_label,
                    style={
                        **NUMERIC,
                        "display": "block",
                        "overflow": "hidden",
                        "textOverflow": "ellipsis",
                        "textAlign": "left",
                        "fontSize": "11px",
                        "fontWeight": "600",
                        "lineHeight": f"{GANTT_BAR_PX}px",
                        "border": "none",
                        "fontFamily": "inherit",
                        "position": "absolute",
                        "zIndex": "1",
                        "top": top,
                        "left": _px(bar.left_px),
                        "width": _px(bar.width_px),
                        "minWidth": "6px",
                        "height": f"{GANTT_BAR_PX}px",
                        "padding": "0 6px",
                        "borderRadius": rx.cond(bar.clipped, "0 4px 4px 0", "4px"),
                        "backgroundColor": BAR_BG,
                        "color": "var(--mantine-color-white)",
                        "cursor": "pointer",
                        "_hover": {"backgroundColor": "var(--mantine-color-blue-7)"},
                        "_focusVisible": {
                            "outline": "2px solid var(--aq-accent)",
                            "outlineOffset": "2px",
                        },
                        "&[data-expanded]": {"boxShadow": SELECTED_RING},
                    },
                ),
            ),
            mn.popover.dropdown(
                _bar_details(row, bar),
                bg="var(--aq-surface-muted)",
            ),
            position="bottom-start",
            width=288,
            shadow="md",
            radius="lg",
            with_arrow=True,
            keep_mounted=True,
        ),
        rx.cond(
            bar.inside,
            rx.fragment(),
            mn.text(
                bar.side_label,
                fz="11px",
                c="var(--aq-text-muted)",
                style={
                    **NUMERIC,
                    "position": "absolute",
                    "top": _px(bar.lane * GANTT_LANE_PX + GANTT_PADDING_PX + 3),
                    "left": _px(bar.left_px + bar.width_px + 6),
                    "pointerEvents": "none",
                },
            ),
        ),
    )


def _month_line(left: rx.Var[int]) -> rx.Component:
    """Month separator inside a lane; drawn there so the week lines don't cover it."""
    return mn.box(
        style={
            "position": "absolute",
            "top": "0",
            "bottom": "0",
            "left": _px(left),
            "borderLeft": MONTH_START_BORDER,
            "pointerEvents": "none",
        },
    )


def _person(row: ObjectVar[AbsenceGanttRow]) -> rx.Component:
    return mn.group(
        mn.avatar(
            name=row.name,
            size=30,
            radius="xl",
            color=row.avatar_color,
            variant="filled",
        ),
        mn.stack(
            mn.text(row.name, fz="13px", fw="600", truncate=True),
            rx.cond(
                row.job_title != "",
                mn.text(
                    row.job_title, fz="12px", c="var(--aq-text-muted)", truncate=True
                ),
            ),
            gap=0,
            miw=0,
        ),
        gap=10,
        wrap="nowrap",
        style={
            **_sticky("left", "var(--aq-surface)"),
            "padding": "0 16px",
            "minWidth": "0",
        },
    )


def _row(row: ObjectVar[AbsenceGanttRow]) -> rx.Component:
    return _grid_row(
        _person(row),
        _AbsenceLane.create(
            rx.foreach(GANTT.month_lines, _month_line),
            rx.foreach(row.bars, lambda bar: _bar(row, bar)),
            day_px=GANTT.day_px,
            days=GANTT.weeks.length() * DAYS_PER_WEEK,
            min_day=GANTT.min_day,
            start_iso=GANTT.horizon_start,
            holidays=GANTT.holiday_days,
            on_select_range=lambda start, end: PlanningAbsenceState.start_absence(
                row.real_id, start, end
            ),
            style={"position": "relative", "backgroundImage": LANE_BG},
        ),
        mn.stack(
            mn.text(row.total_days, fz="13px", fw="650", style=NUMERIC),
            mn.text(row.next_label, fz="11px", c="var(--aq-text-muted)", style=NUMERIC),
            gap=0,
            align="flex-end",
            justify="center",
            style={**_sticky("right", "var(--aq-surface)"), "padding": "0 16px"},
        ),
        style={
            # Above the overlay, so its lines don't show through the borders.
            "position": "relative",
            "zIndex": "1",
            "height": _px(row.height_px),
            "borderBottom": ROW_LINE,
        },
    )


def _empty() -> rx.Component:
    return mn.stack(
        mn.text(
            "Keine Abwesenheiten für den gewählten Zeitraum und Filter.",
            fz="13px",
            c="var(--aq-text-muted)",
        ),
        mn.button(
            "Ganzes Team zeigen",
            variant="light",
            size="xs",
            on_click=PlanningStore.set_absence_show_all(True),  # ty: ignore[invalid-argument-type]
        ),
        align="center",
        gap=10,
        py="xl",
        style={"position": "sticky", "left": "0", "width": "100cqw"},
    )


def _timeline() -> rx.Component:
    return mn.box(
        _header(),
        mn.box(
            _overlay(),
            rx.foreach(GANTT.rows, _row),
            rx.cond(GANTT.rows.length() > 0, rx.fragment(), _empty()),
            style={"position": "relative", "width": _total_width()},
        ),
        _upcoming_section(),
        id="planning-gantt-root",
        style={**GRID_WRAPPER_STYLE, "containerType": "inline-size"},
    )


# === Footer ===


def _legend_item(swatch: dict, label: str) -> rx.Component:
    return mn.group(
        mn.box(style={"width": "18px", "height": "10px", **swatch}),
        mn.text(label, fz="12px", c="var(--aq-text-muted)"),
        gap=6,
        wrap="nowrap",
    )


def _legend() -> rx.Component:
    return mn.group(
        _legend_item({"backgroundColor": BAR_BG, "borderRadius": "3px"}, "Abwesenheit"),
        _legend_item(
            {"border": "1.5px dashed var(--aq-accent)", "borderRadius": "3px"},
            "Neu (ziehen)",
        ),
        _legend_item(
            {"width": "10px", "height": "14px", "backgroundImage": HOLIDAY_HATCH},
            "Feiertag",
        ),
        _legend_item(
            {
                "width": "10px",
                "height": "14px",
                "backgroundColor": WEEKEND_BG,
                "boxShadow": "inset 0 0 0 1px var(--aq-border)",
            },
            "Wochenende",
        ),
        _legend_item(
            {"width": "2px", "height": "14px", "backgroundColor": "var(--aq-negative)"},
            "Heute",
        ),
        mn.text(HINT, fz="12px", c="var(--aq-text-tertiary)", ml="auto"),
        gap="lg",
    )


STATUS = {
    "neg": ("triangle-alert", "var(--aq-negative)", "var(--aq-negative-soft)"),
    "ok": ("circle-check", "var(--aq-positive)", "var(--aq-positive-soft)"),
}


def _status(item: ObjectVar[UpcomingAbsence], key: str) -> rx.Component:
    icon, color, background = STATUS[key]
    return mn.group(
        rx.icon(icon, size=15, style={"flexShrink": "0"}),
        mn.text(item.status_label, fz="12.5px", fw="600"),
        gap=8,
        wrap="nowrap",
        px=10,
        py=6,
        c=color,
        bg=background,
        style={"borderRadius": "8px"},
    )


def _affected(project: ObjectVar[AffectedProject]) -> rx.Component:
    return mn.group(
        mn.box(
            w=8,
            h=8,
            bg=project.color,
            style={"borderRadius": "50%", "flexShrink": "0"},
        ),
        mn.text(project.name, fz="13px", truncate=True, style={"flex": "1"}),
        mn.text(
            project.days_label,
            fz="12.5px",
            fw="600",
            style=NUMERIC,
        ),
        mn.text(
            project.weeks,
            fz="12px",
            c="var(--aq-text-muted)",
            w=72,
            ta="right",
            style=NUMERIC,
        ),
        gap=8,
        wrap="nowrap",
    )


def _upcoming(item: ObjectVar[UpcomingAbsence]) -> rx.Component:
    return mn.stack(
        mn.group(
            mn.avatar(
                name=item.name,
                size=34,
                radius="xl",
                color=item.avatar_color,
                variant="filled",
            ),
            mn.stack(
                mn.text(item.name, fz="14px", fw="650", truncate=True),
                mn.text(
                    item.period, fz="12.5px", c="var(--aq-text-muted)", style=NUMERIC
                ),
                gap=1,
                miw=0,
                style={"flex": "1"},
            ),
            mn.badge(
                item.relative,
                variant="light",
                color=rx.cond(item.is_running, "blue", "gray"),
                radius="xl",
                size="lg",
                tt="none",
                fw=600,
            ),
            gap=12,
            wrap="nowrap",
            align="flex-start",
        ),
        rx.match(
            item.status,
            ("neg", _status(item, "neg")),
            ("ok", _status(item, "ok")),
            mn.text(item.status_label, fz="12.5px", c="var(--aq-text-muted)"),
        ),
        rx.cond(
            item.projects.length() > 0,
            mn.stack(
                mn.text(
                    "Eingeplant in diesen Wochen",
                    fz="11px",
                    fw="650",
                    tt="uppercase",
                    c="var(--aq-text-muted)",
                    style={"letterSpacing": "0.03em"},
                ),
                rx.foreach(item.projects, _affected),
                gap=6,
            ),
        ),
        gap=12,
        p=16,
        bg="var(--aq-surface)",
        style={"borderRadius": "12px", "boxShadow": "0 0 0 1px var(--aq-border)"},
    )


def _upcoming_section() -> rx.Component:
    """Next absences with the projects booked in those weeks.

    Pinned to the visible width of the scroll area, so it never scrolls sideways.
    """
    return rx.cond(
        GANTT.upcoming.length() > 0,
        mn.stack(
            mn.stack(
                mn.text("Nächste Abwesenheiten", fz="15px", fw="650"),
                mn.text(
                    "Welche Projekte in diesen Wochen eingeplant sind und ob die "
                    "Kapazität reicht.",
                    fz="12.5px",
                    c="var(--aq-text-muted)",
                ),
                gap=2,
            ),
            mn.box(
                rx.foreach(GANTT.upcoming, _upcoming),
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fill, minmax(340px, 1fr))",
                    "gap": "12px",
                    "alignItems": "start",
                },
            ),
            gap=12,
            style={
                "position": "sticky",
                "left": "0",
                "width": "100cqw",
                "boxSizing": "border-box",
                "padding": "24px 16px",
            },
        ),
    )


def _footer() -> rx.Component:
    return mn.box(
        _legend(),
        px=16,
        py=10,
        style={"borderTop": "1px solid var(--aq-separator)", "flexShrink": "0"},
    )


def _employee_field() -> rx.Component:
    return mn.select(
        label="Mitarbeiter",
        placeholder="Mitarbeiter wählen",
        data=PlanningStore.employee_select_options,
        value=rx.cond(
            TeamState.selected_employee,
            TeamState.selected_employee.id.to_string(),  # ty: ignore[unresolved-attribute]
            "",
        ),
        on_change=PlanningAbsenceState.pick_employee,
        searchable=True,
        required=True,
        combobox_props={"withinPortal": False},
        w="100%",
    )


def planning_gantt() -> rx.Component:
    return rx.cond(
        PlanningStore.is_loaded,
        mn.box(
            _timeline(),
            _footer(),
            absence_modal(
                on_submit=PlanningAbsenceState.create_absence,
                employee_field=_employee_field(),
            ),
            style={
                "display": "flex",
                "flexDirection": "column",
                "flex": "1",
                "minHeight": "0",
                "width": "100%",
            },
        ),
        mn.center(
            mn.group(rx.spinner(size="3"), mn.text("Lade Abwesenheiten...", size="sm")),
            py="xl",
        ),
    )
