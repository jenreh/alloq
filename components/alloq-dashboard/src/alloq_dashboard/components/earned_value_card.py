"""Portfolio budget forecast card (weekly aggregation, risk band)."""

from __future__ import annotations

from typing import Any

import reflex as rx
from alloq_commons.components.formatters import de_number

import appkit_mantine as mn
from alloq_dashboard.components.drill_down_drawer import DRILL_EARNED_VALUE
from alloq_dashboard.components.kpi_card import kpi_card
from alloq_dashboard.states import BudgetBurnState, DashboardState
from appkit_mantine.charts import CompositeChart


class _CompositeChartFmt(CompositeChart):
    """CompositeChart subclass exposing Mantine's `valueFormatter` prop."""

    value_formatter: rx.Var[Any]


_composite_chart_fmt = _CompositeChartFmt.create


def _kpi_cell(
    label: str,
    value: rx.Component,
    accent: rx.Var[str] | str | None = None,
) -> rx.Component:
    color = "var(--alloq-text)" if accent is None else accent
    return mn.stack(
        mn.text(
            label,
            size="xs",
            fw="600",
            c="var(--alloq-text-muted)",
            style={"letterSpacing": "0.04em", "textTransform": "uppercase"},
        ),
        mn.box(
            value,
            style={
                "fontSize": "1.05rem",
                "fontWeight": "700",
                "color": color,
                "lineHeight": "1.2",
            },
        ),
        gap="2px",
        style={"flex": "1", "minWidth": "0"},
    )


def _eur(value: rx.Var | float, decimals: int = 0) -> rx.Component:
    return de_number(
        value,
        decimal_scale=decimals,
        fixed_decimal_scale=True,
        suffix=" €",
    )


def _summary_row() -> rx.Component:
    data = BudgetBurnState.data
    return mn.group(
        _kpi_cell("Budget", _eur(data.latest_budget)),
        _kpi_cell("Forecast", _eur(data.latest_forecast)),
        _kpi_cell(
            "Abweichung",
            _eur(data.latest_delta_abs),
            accent=rx.cond(
                data.latest_delta_abs > 0,
                "var(--mantine-color-red-7)",
                "var(--mantine-color-green-7)",
            ),
        ),
        gap="lg",
        wrap="wrap",
        align="left",
        w="70%",
    )


_DE_VALUE_FORMATTER = (
    "(v) => {"
    "const f = (x) => new Intl.NumberFormat('de-DE',"
    "{maximumFractionDigits:0}).format(Math.round(Number(x)||0)) + ' €';"
    "return Array.isArray(v) ? v.map(f).join(' - ') : f(v);"
    "}"
)
_DE_TICK_FORMATTER = (
    "(v) => {"
    "const n = Number(v) || 0;"
    "const abs = Math.abs(n);"
    "if (abs >= 1000000) return "
    "(n/1000000).toLocaleString('de-DE',{maximumFractionDigits:1}) + 'M €';"
    "if (abs >= 1000) return "
    "(n/1000).toLocaleString('de-DE',{maximumFractionDigits:1}) + 'T €';"
    "return n.toLocaleString('de-DE') + ' €';"
    "}"
)


def _forecast_chart() -> rx.Component:
    data = BudgetBurnState.data.weekly_forecast
    return _composite_chart_fmt(
        data=data.foreach(
            lambda p: {
                "KW": p.week_label,
                "Risikoband": [p.forecast_min, p.forecast_max],
                "Budget": p.total_budget,
                "Ist-Kosten": p.actual_cost,
                "EAC lin": p.eac_linear,
                "EAC add": p.eac_additive,
            }
        ),
        data_key="KW",
        series=[
            {
                "name": "Risikoband",
                "color": "var(--mantine-color-violet-3)",
                "type": "area",
                "strokeWidth": 0,
                "fillOpacity": 0.22,
                "activeDot": False,
            },
            {
                "name": "Budget",
                "color": "var(--alloq-text)",
                "type": "line",
                "strokeDasharray": "5 5",
            },
            {
                "name": "Ist-Kosten",
                "color": "var(--mantine-color-yellow-7)",
                "type": "line",
            },
            {
                "name": "EAC lin",
                "color": "var(--mantine-color-violet-5)",
                "type": "line",
            },
            {
                "name": "EAC add",
                "color": "var(--mantine-color-violet-8)",
                "type": "line",
            },
        ],
        h=260,
        with_legend=True,
        legend_props={
            "verticalAlign": "bottom",
            "height": 50,
            "wrapperStyle": {"whiteSpace": "nowrap"},
        },
        with_y_axis=True,
        with_x_axis=True,
        grid_axis="y",
        curve_type="monotone",
        x_axis_props={"fontSize": 10, "interval": "preserveStartEnd"},
        y_axis_props={
            "fontSize": 10,
            "width": 70,
            "tickFormatter": rx.Var(_js_expr=_DE_TICK_FORMATTER),
        },
        value_formatter=rx.Var(_js_expr=_DE_VALUE_FORMATTER),
    )


def earned_value_card() -> rx.Component:
    data = BudgetBurnState.data
    body = mn.stack(
        _summary_row(),
        rx.cond(
            data.weekly_forecast.length() > 0,
            _forecast_chart(),
            mn.text("Keine Verlaufsdaten.", size="sm", c="var(--alloq-text-muted)"),
        ),
        gap="md",
    )
    return kpi_card(
        title="Budget Prognosen",
        body=body,
        is_loading=BudgetBurnState.is_loading,
        error_message=BudgetBurnState.error_message,
        icon="trending-up",
        on_open=DashboardState.open_drill_down(DRILL_EARNED_VALUE),
    )
