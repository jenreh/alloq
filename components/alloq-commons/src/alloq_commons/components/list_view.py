"""macOS list (source table) with group rows and a detail inspector.

Rows are CSS grid rows sharing one column template with the sticky header.
The inspector sits on the right of the list (320px) and is hidden on narrow
windows below the list.
"""

from collections.abc import Sequence
from typing import Any

import reflex as rx
from reflex.event import EventType

import appkit_mantine as mn
from alloq_commons import theme


def split_view(
    main: rx.Component, inspector: rx.Component, *, show_inspector: Any = True
) -> rx.Component:
    """List on the left, inspector on the right."""
    return mn.box(
        mn.box(main, class_name="aq-split-main"),
        rx.cond(show_inspector, inspector, rx.fragment()),
        class_name="aq-split",
    )


def _header_cell(
    label: str,
    key: str,
    right: bool,
    *,
    sort_column: rx.Var[str] | None,
    sort_desc: rx.Var[bool] | None,
    on_sort: Any,
) -> rx.Component:
    """One header cell; clickable with a direction arrow when sortable."""
    align = "aq-right" if right else ""
    if not (key and sort_column is not None and on_sort is not None):
        return rx.el.span(label, class_name=align)
    active = sort_column == key
    arrow = (
        rx.cond(active, rx.cond(sort_desc, " ↓", " ↑"), "")
        if sort_desc is not None
        else ""
    )
    return rx.el.span(
        label,
        arrow,
        class_name=align,
        on_click=on_sort(key),
        custom_attrs={
            "data-sort": key,
            "data-sorted": rx.cond(active, "true", "false"),
        },
    )


def list_header(
    columns: Sequence[tuple[str, str, bool]],
    template: str,
    *,
    sort_column: rx.Var[str] | None = None,
    sort_desc: rx.Var[bool] | None = None,
    on_sort: Any = None,
) -> rx.Component:
    """Sticky header; columns are (label, sort key or "", right aligned)."""
    return mn.box(
        *(
            _header_cell(
                label,
                key,
                right,
                sort_column=sort_column,
                sort_desc=sort_desc,
                on_sort=on_sort,
            )
            for label, key, right in columns
        ),
        class_name="aq-thead",
        style={"gridTemplateColumns": template},
        custom_attrs={"role": "row"},
    )


def sticky_block_header(top: str) -> dict[str, str]:
    """Style a section heading to stay below its table header while scrolling."""
    return {"position": "sticky", "top": top, "zIndex": "20"}


def list_group(
    title: str,
    count: rx.Var[int] | int,
    *,
    style: dict[str, str] | None = None,
) -> rx.Component:
    return mn.box(
        title,
        rx.el.span(count, style={"fontWeight": "400"}),
        class_name="aq-group",
        style=style or {},
    )


def list_row(
    *cells: rx.Component,
    template: str,
    selected: rx.Var[bool] | bool,
    on_click: EventType[()],
    **props: Any,
) -> rx.Component:
    return rx.el.button(
        *cells,
        type="button",
        class_name="aq-tr",
        on_click=on_click,
        **props,
        style={"gridTemplateColumns": template},
        custom_attrs={
            "role": "row",
            "aria-selected": rx.cond(selected, "true", "false"),
        },
    )


def cell_main(leading: rx.Component, name: Any, sub: Any = None) -> rx.Component:
    """Leading tile or avatar with name and a muted second line."""
    lines = [rx.el.span(name, class_name="aq-cell-name")]
    if sub is not None:
        lines.append(rx.el.span(sub, class_name="aq-cell-sub"))
    return rx.el.span(
        leading,
        rx.el.span(
            *lines,
            style={"minWidth": "0", "display": "flex", "flexDirection": "column"},
        ),
        class_name="aq-cell-main",
    )


def tile(
    text: Any, color: Any, *, large: bool = False, round_: bool = False
) -> rx.Component:
    """Colored initials tile (projects) or circle (people)."""
    return rx.el.span(
        text,
        class_name="aq-tile",
        custom_attrs={
            "data-size": "lg" if large else "md",
            **({"data-shape": "round"} if round_ else {}),
        },
        style={"background": color},
    )


def badge(label: Any, tone: Any) -> rx.Component:
    """Status badge; tone is positive, negative, warning, info or neutral."""
    return rx.el.span(label, class_name="aq-badge", custom_attrs={"data-tone": tone})


def tag(label: Any) -> rx.Component:
    return rx.el.span(label, class_name="aq-tag")


def meter(percent: Any, color: Any = theme.ACCENT) -> rx.Component:
    """Thin progress bar, 0–100 (clamped by CSS width)."""
    return mn.box(
        mn.box(
            style={
                "width": rx.Var.create(percent).to(str) + "%",
                "maxWidth": "100%",
                "background": color,
            }
        ),
        class_name="aq-meter",
        custom_attrs={"role": "presentation"},
    )


def number(value: Any, *, right: bool = True, **style: Any) -> rx.Component:
    return rx.el.span(
        value,
        class_name="aq-num aq-right" if right else "aq-num",
        style=style,
    )


def inspector(*children: rx.Component, label: str) -> rx.Component:
    return rx.el.aside(*children, class_name="aq-inspector", aria_label=label)


def inspector_section(title: Any, *children: rx.Component) -> rx.Component:
    return mn.stack(
        rx.el.div(title, class_name="aq-insp-title"),
        *children,
        gap=8,
    )


def key_values(*pairs: tuple[str, Any]) -> rx.Component:
    items: list[rx.Component] = []
    for key, value in pairs:
        items.extend((rx.el.dt(key), rx.el.dd(value)))
    return rx.el.dl(*items, class_name="aq-kv")


def plain_button(label: str, on_click: Any, **props: Any) -> rx.Component:
    """White macOS push button."""
    return mn.button(
        label,
        variant="default",
        size="xs",
        h=28,
        radius="md",
        on_click=on_click,
        **props,
    )


def empty_list(text: str) -> rx.Component:
    return mn.text(text, ta="center", c=theme.TEXT_MUTED, fz="13px", py=48, px=22)
