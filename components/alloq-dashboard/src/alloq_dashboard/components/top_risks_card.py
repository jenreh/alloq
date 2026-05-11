"""Top risks KPI card."""

from __future__ import annotations

import reflex as rx
from alloq_commons.components import (
    ROW_STYLE,
)
from alloq_commons.components.formatters import format_date_de
from alloq_commons.entities.risk import RiskMitigationStatus
from alloq_project.states.project_state import ProjectState

import appkit_mantine as mn
from alloq_dashboard.components.kpi_card import kpi_card
from alloq_dashboard.states import RiskState

CRITICAL_RISK_SCORE = 25


def _risk_row(risk: rx.Var) -> rx.Component:
    return mn.group(
        mn.avatar(
            risk.score.to_string(),
            size="md",
            radius="md",
            color=rx.cond(risk.score < CRITICAL_RISK_SCORE, "orange", "red"),
            variant="filled",
        ),
        mn.stack(
            mn.group(
                mn.text(
                    risk.name,
                    size="md",
                    fw="600",
                    c="var(--alloq-text)",
                    style={"flex": "1", "minWidth": 0},
                    truncate="end",
                ),
                mn.badge(
                    rx.match(
                        risk.mitigation_status,
                        (RiskMitigationStatus.OPEN.value, "Offen"),
                        (RiskMitigationStatus.MITIGATED.value, "In Bearbeitung"),
                        (RiskMitigationStatus.RESOLVED.value, "Geschlossen"),
                        risk.mitigation_status,
                    ),
                    size="md",
                    variant="outline",
                    style={"minWidth": "5rem"},
                ),
                gap="sm",
                align="center",
                w="100%",
                wrap="nowrap",
            ),
            mn.group(
                mn.text(
                    risk.project_name,
                    size="xs",
                    c="var(--alloq-text-muted)",
                    style={"flex": "1", "minWidth": 0},
                    truncate="end",
                ),
                rx.cond(
                    risk.updated_at != "",
                    mn.text(
                        format_date_de(risk.updated_at),
                        size="xs",
                        c="var(--alloq-text-muted)",
                        style={"whiteSpace": "nowrap"},
                    ),
                    rx.fragment(),
                ),
                gap="xs",
                align="center",
                w="100%",
                wrap="nowrap",
            ),
            gap="2px",
            flex="1",
        ),
        style={**ROW_STYLE, "cursor": "pointer"},
        on_click=ProjectState.select_project_with_tab(risk.project_id, "risiken"),
    )


def top_risks_card() -> rx.Component:
    data = RiskState.data
    body = mn.box(
        rx.cond(
            data.top_open.length() > 0,
            mn.scroll_area(
                mn.stack(rx.foreach(data.top_open, _risk_row), gap="xs"),
                type="auto",
                scrollbar_size=6,
                h="100%",
                w="100%",
            ),
            mn.text("Keine offenen Risiken.", size="sm", c="var(--alloq-text-muted)"),
        ),
        style={
            "flex": "1",
            "minHeight": "0",
            "display": "flex",
            "flexDirection": "column",
            "width": "100%",
        },
    )
    return kpi_card(
        title="Kritische Risiken",
        body=body,
        is_loading=RiskState.is_loading,
        error_message=RiskState.error_message,
        icon="shield-alert",
    )
