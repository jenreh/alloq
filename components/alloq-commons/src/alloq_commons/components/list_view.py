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

INSPECTOR_WIDTH_PX = 320

LIST_CSS = (
    ".aq-split{display:flex;flex:1;min-height:0;}"
    f".aq-split-main{{flex:1;min-width:0;overflow:auto;background:{theme.SURFACE};}}"
    f".aq-inspector{{width:{INSPECTOR_WIDTH_PX}px;flex-shrink:0;overflow:auto;"
    f"border-left:1px solid {theme.BORDER};background:{theme.BACKGROUND};"
    "padding:20px;display:flex;flex-direction:column;gap:18px;}"
    ".aq-thead,.aq-tr{display:grid;align-items:center;column-gap:12px;"
    "padding:0 22px;}"
    ".aq-thead{box-sizing:border-box;height:30px;position:sticky;top:0;z-index:30;"
    f"background:{theme.SURFACE};border-bottom:1px solid {theme.BORDER};"
    f"font-size:11.5px;color:{theme.TEXT_MUTED};}}"
    ".aq-thead [data-sort]{cursor:default;user-select:none;}"
    f".aq-thead [data-sorted=true]{{color:{theme.TEXT};font-weight:500;}}"
    f'.aq-thead [data-sort="total_pt"]{{color:{theme.TEXT};font-weight:600;}}'
    ".aq-tfoot{display:grid;align-items:center;column-gap:12px;padding:0 22px;"
    "min-width:640px;min-height:46px;position:sticky;bottom:0;z-index:2;"
    "container-type:scroll-state;"
    f"background:{theme.SURFACE};border-top:1px solid {theme.BORDER};"
    "font-weight:600;}"
    ".aq-tfoot .aq-num{font-size:inherit;}"
    f".aq-tfoot::after{{content:'';position:absolute;left:0;right:0;"
    f"bottom:0;border-bottom:1px solid {theme.BORDER};pointer-events:none;}}"
    "@container scroll-state(stuck: bottom){.aq-tfoot::after{display:none;}}"
    f".aq-tr{{min-height:46px;border-bottom:1px solid {theme.SEPARATOR};"
    f"background:{theme.SURFACE};cursor:default;width:100%;text-align:left;"
    f"border-left:0;border-right:0;border-top:0;font:inherit;color:{theme.TEXT};}}"
    f".aq-tr:hover{{background:{theme.HOVER};}}"
    f".aq-tr[aria-selected=true]{{background:{theme.ACCENT_SOFT};}}"
    f".aq-tr:focus-visible{{outline:2px solid {theme.ACCENT};outline-offset:-2px;}}"
    ".aq-group{display:flex;align-items:center;gap:8px;height:30px;"
    f"padding:0 22px;background:{theme.SURFACE_MUTED};"
    f"border-bottom:1px solid {theme.BORDER};font-size:11.5px;font-weight:600;"
    f"color:{theme.TEXT_MUTED};}}"
    ".aq-right{text-align:right;justify-self:end;}"
    ".aq-cell-main{display:flex;align-items:center;gap:10px;min-width:0;}"
    ".aq-cell-name{font-weight:500;font-size:13px;white-space:nowrap;"
    "overflow:hidden;text-overflow:ellipsis;}"
    f".aq-cell-sub{{font-size:11.5px;color:{theme.TEXT_MUTED};white-space:nowrap;"
    "overflow:hidden;text-overflow:ellipsis;}"
    ".aq-num{font-variant-numeric:tabular-nums;font-size:12.5px;white-space:nowrap;}"
    f".aq-meter{{height:5px;border-radius:3px;background:{theme.token('meter-track')};"
    "overflow:hidden;flex:1;}"
    ".aq-meter>div{height:100%;border-radius:3px;}"
    ".aq-insp-title{font-size:11.5px;font-weight:600;color:" + theme.TEXT_MUTED + ";}"
    ".aq-kv{display:grid;grid-template-columns:110px 1fr;row-gap:8px;"
    "column-gap:8px;font-size:12.5px;margin:0;align-items:start;}"
    f".aq-kv dt{{color:{theme.TEXT_MUTED};margin:0;}}"
    ".aq-kv dd{margin:0;font-variant-numeric:tabular-nums;min-width:0;"
    "overflow-wrap:anywhere;}"
    ".aq-badge{display:inline-flex;align-items:center;gap:5px;height:20px;"
    "padding:0 8px;border-radius:10px;font-size:11.5px;font-weight:500;"
    "white-space:nowrap;}"
    ".aq-badge::before{content:'';width:6px;height:6px;border-radius:50%;"
    "background:currentColor;}"
    + "".join(
        f".aq-badge[data-tone={tone}]{{background:{theme.token(tone + '-soft')};"
        f"color:{theme.token(tone)};}}"
        for tone in ("positive", "negative", "warning", "info")
    )
    + f".aq-badge[data-tone=neutral]{{background:{theme.token('tag')};"
    f"color:{theme.token('tag-text')};}}"
    f".aq-tag{{display:inline-flex;align-items:center;height:18px;padding:0 6px;"
    f"border-radius:5px;background:{theme.token('tag')};"
    f"color:{theme.token('tag-text')};font-size:10.5px;font-weight:600;"
    "letter-spacing:.02em;white-space:nowrap;}"
    ".aq-tile{width:28px;height:28px;border-radius:7px;display:grid;"
    "place-items:center;color:#fff;font-size:11px;font-weight:650;flex-shrink:0;}"
    ".aq-tile[data-size=lg]{width:44px;height:44px;border-radius:11px;"
    "font-size:15px;}"
    ".aq-tile[data-shape=round]{border-radius:50%;}"
    "@media (max-width: 1100px){.aq-inspector{width:280px;}}"
    "@media (max-width: 820px){.aq-split{flex-direction:column;overflow:auto;}"
    ".aq-split-main{overflow:visible;flex:none;}"
    ".aq-inspector{width:auto;border-left:0;"
    f"border-top:1px solid {theme.BORDER};overflow:visible;}}"
    ".aq-thead,.aq-tr{min-width:640px;}}"
)


def split_view(
    main: rx.Component, inspector: rx.Component, *, show_inspector: Any = True
) -> rx.Component:
    """List on the left, inspector on the right."""
    return mn.box(
        rx.el.style(LIST_CSS),
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
