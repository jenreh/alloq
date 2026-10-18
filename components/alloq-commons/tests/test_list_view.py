"""Tests for the macOS list building blocks."""

from pathlib import Path

import reflex as rx
from alloq_commons.components import list_view

ASSETS_CSS = Path(__file__).parents[3] / "assets" / "css"


def _css(name: str) -> str:
    return (ASSETS_CSS / name).read_text()


def test_css_defines_tones_and_responsive_inspector() -> None:
    for tone in ("positive", "negative", "warning", "info", "neutral"):
        assert f"data-tone={tone}" in _css("aq-list.css")
    assert "@media (max-width: 820px)" in _css("aq-list.css")
    assert "font-size: 12.5px;" in _css("aq-list.css")
    assert _css("aq-list.css").count("{") == _css("aq-list.css").count("}")


def test_sticky_table_header_stays_above_group_headings() -> None:
    header_css = _css("aq-list.css").split(".aq-thead {", 1)[1].split("}", 1)[0]

    assert "box-sizing: border-box" in header_css
    assert "height: 30px" in header_css
    assert "z-index: 30" in header_css
    assert f"background: {list_view.theme.SURFACE};" in header_css


def test_header_marks_sorted_column() -> None:
    rendered = str(
        list_view.list_header(
            [("Name", "name", False), ("Budget", "budget", True), ("Team", "", False)],
            "1fr 1fr 1fr",
            sort_column=rx.Var.create("name"),
            sort_desc=rx.Var.create(False),
            on_sort=rx.console_log,
        )
    )
    assert "data-sort" in rendered
    assert "aq-right" in rendered
    assert "1fr 1fr 1fr" in rendered


def test_header_without_sorting() -> None:
    rendered = str(list_view.list_header([("Name", "", False)], "1fr"))
    assert "data-sort" not in rendered


def test_row_is_a_selectable_button() -> None:
    rendered = str(
        list_view.list_row(
            rx.text("zelle"),
            template="1fr",
            selected=True,
            on_click=rx.console_log("x"),
        )
    )
    assert "aria-selected" in rendered
    assert "aq-tr" in rendered


def test_building_blocks_render() -> None:
    parts = [
        list_view.split_view(rx.text("liste"), rx.text("inspektor")),
        list_view.list_group("Gruppe", 3),
        list_view.cell_main(rx.text("t"), "Name", "Sub"),
        list_view.cell_main(rx.text("t"), "Name"),
        list_view.tile("AB", "#2E6BD6", large=True, round_=True),
        list_view.badge("Aktiv", "positive"),
        list_view.tag("DS"),
        list_view.meter(40),
        list_view.number(12, right=False),
        list_view.inspector(rx.text("x"), label="Details"),
        list_view.inspector_section("Titel", rx.text("y")),
        list_view.key_values(("Kunde", "Acme")),
        list_view.plain_button("Bearbeiten", rx.console_log("x")),
        list_view.empty_list("Leer"),
    ]
    rendered = " ".join(str(p) for p in parts)
    for text in ("liste", "inspektor", "Gruppe", "aq-badge", "Acme", "Leer", "Details"):
        assert text in rendered


def test_round_tile_is_a_circle_via_css() -> None:
    round_tile = str(list_view.tile("AB", "#2E6BD6", round_=True))
    square_tile = str(list_view.tile("AB", "#2E6BD6"))
    assert "data-shape" in round_tile
    assert "data-shape" not in square_tile
    rule = _css("aq-list.css").split(".aq-tile[data-shape=round] {")[1]
    assert "border-radius: 50%;" in rule


def test_group_accepts_sticky_header_style() -> None:
    rendered = str(
        list_view.list_group(
            "Gruppe",
            3,
            style=list_view.sticky_block_header("30px"),
        )
    )

    assert '["position"] : "sticky"' in rendered
    assert '["top"] : "30px"' in rendered
