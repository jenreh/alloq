from collections.abc import Sequence

import reflex as rx

import appkit_mantine as mn

_TITLE_OPTICAL_OFFSET = "-0.09em"


def _nav_segments(nav_path: str | Sequence[str]) -> list[str]:
    if isinstance(nav_path, str):
        return [nav_path]
    return list(nav_path)


def _nav_path(nav_path: str | Sequence[str]) -> rx.Component:
    nav_items: list[rx.Component] = []
    for index, segment in enumerate(_nav_segments(nav_path)):
        if index > 0:
            nav_items.append(
                rx.icon(
                    "chevron-right",
                    color="var(--alloq-text-muted)",
                    size=14,
                )
            )
        nav_items.append(
            mn.text(
                segment,
                c="var(--alloq-text-muted)",
                size="sm",
                ta="left",
            )
        )

    return mn.group(
        *nav_items,
        align="center",
        gap="xs",
        w="100%",
    )


def page_header(
    title: str,
    description: str | None = None,
    nav_path: str | Sequence[str] = "",
    **kwargs,
) -> rx.Component:
    """Warm page header with breadcrumb, title, and optional description."""
    inner_children: list[rx.Component] = [
        rx.cond(nav_path != "", _nav_path(nav_path)),
        mn.text(
            title,
            c="var(--alloq-text)",
            fw="280",
            m="0",
            p="0",
            size="3rem",
            ta="left",
            style={
                "display": "block",
                "letter_spacing": "0",
                "line_height": "1.08",
                "max_width": "600px",
                "text_wrap": "balance",
                "transform": f"translateX({_TITLE_OPTICAL_OFFSET})",
                "transform_origin": "left center",
            },
        ),
    ]
    if description is not None:
        inner_children.append(
            mn.text(
                description,
                c="var(--alloq-text-muted)",
                m="0",
                p="0",
                ta="left",
                style={
                    "display": "block",
                    "line_height": "1.25",
                    "max_width": "432px",
                },
            )
        )
    outer_kwargs: dict[str, str] = {
        "align": "stretch",
        "gap": "0",
        "w": "100%",
        "pt": "1rem",
        "pb": "3rem",
    }
    outer_kwargs.update(kwargs)
    return mn.stack(
        mn.stack(
            *inner_children,
            align="flex-start",
            gap="md",
            w="100%",
        ),
        **outer_kwargs,
    )
