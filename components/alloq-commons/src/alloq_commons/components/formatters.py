"""Common formatters for the application."""

import reflex as rx

import appkit_mantine as mn


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
