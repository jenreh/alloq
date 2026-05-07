import reflex as rx
from alloq_commons.components.forms import section
from alloq_commons.models.project import Risk, RiskMatrixCell
from alloq_project.states.project_state import ProjectState

import appkit_mantine as mn

_RISK_STATUS_OPTIONS = ["Offen", "In Bearbeitung", "Geschlossen"]
_PROBABILITY_OPTIONS = ["1", "2", "3", "4", "5"]

_SCORE_LOW = 4
_SCORE_MEDIUM = 9
_SCORE_HIGH = 15


def _status_badge_color(status: rx.Var) -> rx.Var:
    """Return a Mantine color name based on mitigation status."""
    return rx.cond(
        status == "Geschlossen",
        "green",
        rx.cond(status == "In Bearbeitung", "yellow", "red"),
    )


def _score_badge_color(score: rx.Var) -> rx.Var:
    """Return a Mantine color name based on risk score."""
    return rx.cond(
        score <= _SCORE_LOW,
        "gray",
        rx.cond(
            score <= _SCORE_MEDIUM,
            "yellow",
            rx.cond(score <= _SCORE_HIGH, "orange", "red"),
        ),
    )


def _matrix_cell(cell: RiskMatrixCell) -> rx.Component:
    """Render one cell of the 5x5 risk matrix."""
    return mn.box(
        mn.group(
            rx.foreach(
                cell.risk_numbers,
                lambda n, i: mn.tooltip(
                    mn.badge(
                        n.to_string(),
                        variant="filled",
                        radius="xl",
                        size="sm",
                        style={
                            "backgroundColor": "var(--alloq-text)",
                            "color": "var(--alloq-bg)",
                            "fontWeight": "700",
                            "minWidth": "1.6rem",
                            "textAlign": "center",
                            "cursor": "default",
                        },
                    ),
                    label=cell.risk_names[i],
                    position="top",
                    with_arrow=True,
                ),
            ),
            gap="4px",
            wrap="wrap",
            align="center",
            justify="center",
        ),
        style={
            "backgroundColor": cell.color,
            "borderRadius": "6px",
            "padding": "8px 4px",
            "minHeight": "3rem",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
        },
    )


def _risk_matrix() -> rx.Component:
    """5x5 risk matrix with colored zones and numbered risk circles."""
    return section(
        mn.stack(
            mn.text("Risikomatrix", size="sm", fw="700", c="dimmed"),
            mn.text(
                "Wahrscheinlichkeit x Auswirkung",
                size="xs",
                c="dimmed",
            ),
            mn.group(
                mn.flex(
                    rx.foreach(
                        ["5", "4", "3", "2", "1"],
                        lambda label: mn.text(
                            label,
                            size="xs",
                            c="dimmed",
                            style={
                                "height": "3.5rem",
                                "display": "flex",
                                "alignItems": "center",
                                "justifyContent": "flex-end",
                                "paddingRight": "6px",
                                "fontWeight": "600",
                            },
                        ),
                    ),
                    direction="column",
                    gap="4px",
                    style={"width": "1.5rem", "flexShrink": "0"},
                ),
                mn.simple_grid(
                    rx.foreach(ProjectState.risk_matrix_cells, _matrix_cell),
                    cols=5,
                    spacing="4px",
                    style={"flex": "1"},
                ),
                align="stretch",
                w="100%",
                gap="0",
            ),
            mn.group(
                mn.box(style={"width": "1.5rem"}),
                mn.group(
                    rx.foreach(
                        ["1", "2", "3", "4", "5"],
                        lambda label: mn.text(
                            label,
                            size="xs",
                            c="dimmed",
                            style={
                                "flex": "1",
                                "textAlign": "center",
                                "fontWeight": "600",
                            },
                        ),
                    ),
                    gap="4px",
                    style={"flex": "1"},
                ),
                w="100%",
                gap="0",
            ),
            mn.group(
                mn.text(
                    "Auswirkung →",
                    size="xs",
                    c="dimmed",
                    style={"flex": "1", "textAlign": "right"},
                ),
                w="100%",
            ),
            gap="xs",
            w="100%",
        ),
    )


def _risk_edit_form() -> rx.Component:
    """Inline edit form bound to risk draft state vars."""
    return mn.stack(
        mn.text_input(
            label="Titel",
            default_value=ProjectState.risk_draft_name,
            on_change=ProjectState.set_risk_draft_name,
            size="sm",
            w="100%",
        ),
        mn.textarea(
            label="Beschreibung",
            default_value=ProjectState.risk_draft_description,
            on_change=ProjectState.set_risk_draft_description,
            size="xs",
            min_rows=2,
            auto_size=True,
            w="100%",
        ),
        mn.textarea(
            label="Maßnahme",
            default_value=ProjectState.risk_draft_measures,
            on_change=ProjectState.set_risk_draft_measures,
            size="xs",
            min_rows=2,
            auto_size=True,
            w="100%",
        ),
        mn.simple_grid(
            mn.select(
                label="Impact (1-5)",
                data=_PROBABILITY_OPTIONS,
                value=ProjectState.risk_draft_impact.to(str),
                on_change=ProjectState.set_risk_draft_impact,
                size="xs",
                clearable=False,
                allow_deselect=False,
            ),
            mn.select(
                label="Probability (1-5)",
                data=_PROBABILITY_OPTIONS,
                value=ProjectState.risk_draft_probability.to(str),
                on_change=ProjectState.set_risk_draft_probability,
                size="xs",
                clearable=False,
                allow_deselect=False,
            ),
            mn.select(
                label="Status",
                data=_RISK_STATUS_OPTIONS,
                value=ProjectState.risk_draft_mitigation_status,
                on_change=ProjectState.set_risk_draft_mitigation_status,
                size="xs",
                clearable=False,
                allow_deselect=False,
            ),
            cols=3,
            spacing="sm",
            w="100%",
        ),
        mn.group(
            mn.button(
                "Speichern",
                left_section=rx.icon("save", size=14),
                size="xs",
                variant="filled",
                gap="4px",
                on_click=ProjectState.save_risk_draft,
            ),
            mn.button(
                "Abbrechen",
                size="xs",
                variant="subtle",
                color="gray",
                on_click=ProjectState.collapse_risk_edit,
            ),
            gap="sm",
            align="center",
            justify="end",
            pt="xs",
        ),
        gap="xs",
        w="100%",
        style={
            "borderTop": "1px solid var(--alloq-border)",
            "marginTop": "8px",
            "paddingTop": "12px",
        },
    )


def _risk_row(risk: Risk) -> rx.Component:
    """Compact risk row with expand/collapse inline edit form."""
    is_expanded = ProjectState.expanded_risk_id == risk.id
    return mn.box(
        mn.group(
            mn.badge(
                risk.number.to(str),
                variant="filled",
                radius="xl",
                size="sm",
                style={
                    "backgroundColor": "var(--alloq-text)",
                    "color": "var(--alloq-bg)",
                    "minWidth": "1.6rem",
                    "textAlign": "center",
                    "flexShrink": "0",
                },
            ),
            mn.text(
                risk.name,
                size="sm",
                fw="600",
                style={
                    "flex": "1",
                    "minWidth": "0",
                    "overflow": "hidden",
                    "textOverflow": "ellipsis",
                    "whiteSpace": "nowrap",
                },
            ),
            mn.badge(
                risk.mitigation_status,
                variant="light",
                radius="sm",
                size="xs",
                color=_status_badge_color(risk.mitigation_status),
                style={"flexShrink": "0"},
            ),
            mn.badge(
                risk.risiko_score.to(str),
                variant="filled",
                radius="sm",
                size="xs",
                color=_score_badge_color(risk.risiko_score),
                style={"flexShrink": "0", "minWidth": "1.4rem", "textAlign": "center"},
            ),
            mn.action_icon(
                rx.cond(
                    is_expanded,
                    rx.icon("chevron_up", size=14),
                    rx.icon("chevron_down", size=14),
                ),
                variant="subtle",
                size="sm",
                on_click=ProjectState.expand_risk(risk.id),
            ),
            mn.action_icon(
                rx.icon("trash_2", size=14),
                variant="subtle",
                color="red",
                size="sm",
                on_click=ProjectState.delete_project_risk(risk.id),
            ),
            w="100%",
            align="center",
            gap="xs",
        ),
        rx.cond(
            is_expanded,
            _risk_edit_form(),
            rx.fragment(),
        ),
        style={
            "backgroundColor": "var(--alloq-item-bg, var(--alloq-surface-muted))",
            "borderRadius": "8px",
            "padding": "10px 12px",
            "cursor": "pointer",
        },
        on_click=ProjectState.expand_risk(risk.id),
    )


def _new_risk_form() -> rx.Component:
    """Inline form for creating a new risk (shown when expanded_risk_id == -1)."""
    return mn.box(
        mn.group(
            mn.badge(
                "+",
                variant="filled",
                radius="xl",
                size="sm",
                style={
                    "backgroundColor": "var(--alloq-text)",
                    "color": "var(--alloq-bg)",
                    "minWidth": "1.6rem",
                    "textAlign": "center",
                    "flexShrink": "0",
                },
            ),
            mn.text(
                "Neues Risiko",
                size="sm",
                fw="600",
                c="dimmed",
                style={"flex": "1"},
            ),
            w="100%",
            align="center",
            gap="xs",
        ),
        _risk_edit_form(),
        style={
            "backgroundColor": "var(--alloq-item-bg, var(--alloq-surface-muted))",
            "borderRadius": "8px",
            "padding": "10px 12px",
        },
    )


def _risk_list() -> rx.Component:
    """Scrollable list of risks with expand-to-edit pattern."""
    return section(
        mn.stack(
            mn.group(
                mn.text("Risiken", size="sm", fw="700", c="dimmed"),
                mn.badge(
                    ProjectState.risks.length().to(str),
                    variant="light",
                    radius="sm",
                    size="sm",
                ),
                mn.box(style={"flex": "1"}),
                mn.button(
                    "Risiko hinzufügen",
                    left_section=rx.icon("plus", size=14),
                    variant="filled",
                    size="xs",
                    gap="4px",
                    on_click=ProjectState.add_project_risk,
                ),
                gap="xs",
                align="center",
                w="100%",
            ),
            rx.cond(
                ProjectState.expanded_risk_id == -1,
                _new_risk_form(),
                rx.fragment(),
            ),
            rx.cond(
                ProjectState.risks.length() > 0,
                mn.stack(
                    rx.foreach(ProjectState.sorted_risks, _risk_row),
                    gap="xs",
                    w="100%",
                ),
                rx.cond(
                    ProjectState.expanded_risk_id == -1,
                    rx.fragment(),
                    mn.text(
                        "Noch keine Risiken erfasst.",
                        size="sm",
                        c="dimmed",
                        ta="center",
                        py="sm",
                    ),
                ),
            ),
            gap="sm",
            w="100%",
        ),
    )


def risiken_tab() -> rx.Component:
    """Risiken tab: risk matrix and editable risk list."""
    return mn.stack(
        _risk_matrix(),
        _risk_list(),
        mn.space(h="2rem"),
        gap="md",
        w="100%",
        class_name="alloq-modal-scroll",
    )
