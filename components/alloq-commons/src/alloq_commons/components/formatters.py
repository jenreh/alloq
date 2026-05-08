"""Common formatters for the application."""

import reflex as rx

import appkit_mantine as mn

ROW_STYLE: dict[str, str] = {
    "padding": "8px 12px",
    "borderRadius": "6px",
    "backgroundColor": "var(--alloq-surface-muted)",
}


def big_number(value: rx.Var, suffix: str = "") -> rx.Component:
    """Render a large KPI number with optional suffix."""
    return mn.group(
        mn.text(
            value.to_string(),
            size="2.25rem",
            fw="700",
            c="var(--alloq-text)",
            style={"lineHeight": "1.0"},
        ),
        rx.cond(
            suffix != "",
            mn.text(suffix, size="md", c="var(--alloq-text-muted)"),
            rx.fragment(),
        ),
        gap="xs",
        align="baseline",
    )


def format_date_de(date_var: rx.Var) -> rx.Var[str]:
    """Format ISO date string (YYYY-MM-DD) to German format (DD.MM.YYYY)."""
    parts = date_var.to(str).split("-")
    return parts[2] + "." + parts[1] + "." + parts[0]


def format_date_de_named(date_var: rx.Var) -> rx.Var[str]:
    """Format ISO date string (YYYY-MM-DD) to German named format (DD. Mon YYYY)."""
    parts = date_var.to(str).split("-")
    month_name = rx.match(
        parts[1],
        ("01", "Jan"),
        ("02", "Feb"),
        ("03", "März"),
        ("04", "Apr"),
        ("05", "Mai"),
        ("06", "Juni"),
        ("07", "Juli"),
        ("08", "Aug"),
        ("09", "Sep"),
        ("10", "Okt"),
        ("11", "Nov"),
        ("12", "Dez"),
        "",
    )
    return f"{parts[2]}. {month_name} {parts[0]}"


def de_number(
    value: rx.Var | float | str,
    *,
    decimal_scale: int | None = None,
    fixed_decimal_scale: bool | rx.Var[bool] | None = None,
    minimum_fraction_digits: int | None = None,
    maximum_fraction_digits: int | None = None,
    suffix: str = "",
    prefix: str = "",
    style: dict[str, str] | None = None,
    **kwargs,
) -> rx.Component:
    """A common number formatter configured for German locales (e.g. 1.000,50)."""
    return mn.number_formatter(
        value=value,
        thousand_separator=".",
        decimal_separator=",",
        decimal_scale=decimal_scale,
        fixed_decimal_scale=fixed_decimal_scale,
        minimum_fraction_digits=minimum_fraction_digits,
        maximum_fraction_digits=maximum_fraction_digits,
        suffix=suffix,
        prefix=prefix,
        style=style,
        **kwargs,
    )
