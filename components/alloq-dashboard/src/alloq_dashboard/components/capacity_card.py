"""Free capacity section card."""

from __future__ import annotations

import reflex as rx
from alloq_commons.components.formatters import de_number

import appkit_mantine as mn
from alloq_dashboard.states import RoleCapacityState


def stat_pill(
    label: str,
    value: rx.Var,
    color: str = "var(--alloq-text)",
) -> rx.Component:
    """Render a label/value metric pill used in cards."""
    return mn.stack(
        mn.text(label, size="xs", c="var(--alloq-text-muted)"),
        mn.text(value.to_string(), size="lg", fw="700", c=color),
        gap="2px",
    )


def _role_capacity_card(role: rx.Var) -> rx.Component:
    """Role capacity card matching project card design."""
    return mn.box(
        mn.card(
            mn.stack(
                mn.group(
                    mn.text(
                        role.role_name,
                        size="md",
                        fw="800",
                        c="var(--alloq-text)",
                        truncate=True,
                        w="50%",
                    ),
                    mn.group(
                        mn.stack(
                            mn.text(
                                "PT FREI",
                                size="xs",
                                c="var(--alloq-text-muted)",
                                nowrap=True,
                            ),
                            de_number(
                                value=role.free_days,
                                minimum_fraction_digits=2,
                                maximum_fraction_digits=2,
                                style={
                                    "fontSize": "var(--mantine-font-size-lg)",
                                    "fontWeight": "700",
                                },
                            ),
                            gap="2px",
                            flex="1 1 0",
                        ),
                        mn.stack(
                            mn.text(
                                "PT GEPLANT",
                                size="xs",
                                c="var(--alloq-text-muted)",
                                nowrap=True,
                            ),
                            de_number(
                                value=role.allocated_days,
                                minimum_fraction_digits=2,
                                maximum_fraction_digits=2,
                                style={
                                    "fontSize": "var(--mantine-font-size-lg)",
                                    "fontWeight": "700",
                                },
                            ),
                            gap="2px",
                            flex="1 1 0",
                        ),
                        mn.stack(
                            stat_pill(
                                "Mitarbeiter",
                                role.employee_count,
                            ),
                            flex="1 1 0",
                        ),
                        justify="end",
                        nowrap=True,
                        w="42%",
                    ),
                    justify="space-between",
                    align="top",
                    w="100%",
                    wrap="nowrap",
                ),
                rx.cond(
                    role.weeks.length() > 0,
                    mn.area_chart(
                        data=role.weeks.foreach(
                            lambda p: {"label": p.label, "Frei": p.value}
                        ),
                        data_key="label",
                        series=[
                            {"name": "Frei", "color": "var(--mantine-color-green-6)"}
                        ],
                        h=120,
                        with_legend=False,
                        with_y_axis=False,
                        grid_axis="none",
                        tick_line="none",
                        x_axis_props={"fontSize": 10},
                        dot_props={"r": 4},
                        unit=" PT",
                    ),
                    rx.fragment(),
                ),
                gap="md",
            ),
            padding="lg",
            radius="lg",
            with_border=False,
            bg="transparent",
        ),
        style={
            "backgroundColor": "var(--alloq-fade-bg)",
            "borderRadius": "var(--mantine-radius-lg)",
        },
    )


def role_capacity_cards() -> rx.Component:
    data = RoleCapacityState.data
    return mn.stack(
        mn.text("Freie Kapazität", size="lg", fw="700", c="var(--alloq-text)"),
        rx.cond(
            data.rows.length() > 0,
            mn.simple_grid(
                rx.foreach(data.rows, _role_capacity_card),
                cols={"base": 1, "sm": 2},
                spacing="lg",
                w="100%",
            ),
            mn.text("Keine Rollen verfügbar.", size="sm", c="var(--alloq-text-muted)"),
        ),
        gap="md",
        w="100%",
    )
