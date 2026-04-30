"""
UI Components — canonical appkit_mantine patterns for KnowledgeAI-Admin.

Derived from: knai-hours capacity_table.py + import_section.py,
              knai-team components.py, app/components/stat_card.py.

Rules:
  - Use mn.* for all visible UI (layout, typography, inputs, feedback).
  - rx.cond / rx.foreach / rx.icon are fine anywhere.
  - Never use rx.vstack, rx.hstack, rx.box where a Mantine equivalent exists.
"""

import appkit_mantine as mn
import reflex as rx

from knai_myfeature.state.my_feature_state import MyFeatureState


# ─── Atom components ──────────────────────────────────────────────────────────


def stat_card(
    title: str,
    value: rx.Var | str | int,
    icon: str,
    color: str = "blue",
) -> rx.Component:
    """Single KPI card with icon and value. Pass state vars for reactivity."""
    return mn.card(
        mn.group(
            mn.action_icon(
                rx.icon(tag=icon, size=22, color="white"),
                variant="filled",
                color=color,
                size="xl",
                radius="md",
            ),
            mn.stack(
                mn.text(title, size="2", c="dimmed"),
                mn.heading(value, size="6", fw="bold"),
                gap="2",
            ),
            gap="md",
            align="center",
        ),
        shadow="sm",
        padding="md",
        radius="md",
        with_border=True,
        w="100%",
    )


def badge_status(label: str, color: str = "blue") -> rx.Component:
    """Inline status badge."""
    return mn.badge(label, color=color, variant="light", size="sm")


def section_heading(title: str, subtitle: str = "") -> rx.Component:
    """Section title block."""
    return mn.stack(
        mn.heading(title, size="4", fw=600),
        mn.text(subtitle, size="2", c="dimmed") if subtitle else rx.fragment(),
        gap="1",
    )


# ─── Filter bar ───────────────────────────────────────────────────────────────


def _filter_bar() -> rx.Component:
    """Search input + year/month selects + clear button."""
    return mn.group(
        mn.text_input(
            value=MyFeatureState.search_query,
            on_change=MyFeatureState.set_search_query,
            placeholder="Suchen...",
            left_section=rx.icon(tag="search", size=16),
            w=240,
        ),
        mn.select(
            data=[str(y) for y in range(2024, 2029)],
            value=MyFeatureState.selected_year_str,
            on_change=MyFeatureState.set_year,
            w=100,
        ),
        mn.select(
            data=[{"value": str(m), "label": name} for m, name in [
                (1, "Jan"), (2, "Feb"), (3, "Mär"), (4, "Apr"),
                (5, "Mai"), (6, "Jun"), (7, "Jul"), (8, "Aug"),
                (9, "Sep"), (10, "Okt"), (11, "Nov"), (12, "Dez"),
            ]],
            value=MyFeatureState.selected_month_str,
            on_change=MyFeatureState.set_month,
            w=100,
        ),
        mn.button(
            "Zurücksetzen",
            on_click=MyFeatureState.load_items,
            variant="subtle",
            size="2",
        ),
        gap="sm",
        align="center",
        wrap="wrap",
    )


# ─── Data table ───────────────────────────────────────────────────────────────


def _table_row(item) -> rx.Component:
    """One row in the items table."""
    return mn.table.tr(
        mn.table.td(mn.text(item.name, size="2")),
        mn.table.td(mn.text(item.formatted_date, size="2", c="dimmed")),
        mn.table.td(
            badge_status(item.status, item.status_color),
        ),
        mn.table.td(
            mn.group(
                mn.action_icon(
                    rx.icon(tag="pencil", size=16),
                    variant="subtle",
                    on_click=MyFeatureState.select_item(item.id),
                ),
                mn.action_icon(
                    rx.icon(tag="trash-2", size=16),
                    variant="subtle",
                    color="red",
                    on_click=MyFeatureState.delete_item(item.id),
                ),
                gap="xs",
            ),
        ),
    )


def _items_table() -> rx.Component:
    """Full table with sticky header."""
    return mn.scroll_area(
        mn.table(
            mn.table.thead(
                mn.table.tr(
                    mn.table.th("Name"),
                    mn.table.th("Datum"),
                    mn.table.th("Status"),
                    mn.table.th(""),
                ),
            ),
            mn.table.tbody(
                rx.foreach(MyFeatureState.filtered_items, _table_row),
            ),
            striped=True,
            highlight_on_hover=True,
            w="100%",
        ),
        h=480,
        type="auto",
    )


def _empty_state() -> rx.Component:
    return mn.card(
        mn.stack(
            rx.icon(tag="inbox", size=40, color="gray"),
            mn.text("Keine Einträge gefunden", size="3", c="dimmed"),
            align="center",
            gap="sm",
        ),
        padding="xl",
        radius="md",
        w="100%",
    )


# ─── Charts ───────────────────────────────────────────────────────────────────


def monthly_bar_chart() -> rx.Component:
    """Stacked bar chart for monthly data."""
    return mn.card(
        mn.stack(
            section_heading("Monatsübersicht"),
            mn.bar_chart(
                data=MyFeatureState.chart_data,
                data_key="month",
                series=[
                    {"name": "Billable", "color": "blue.5"},
                    {"name": "Intern",   "color": "gray.4"},
                ],
                chart_type="stacked",
                with_legend=True,
                with_tooltip=True,
                h=260,
                w="100%",
            ),
            gap="md",
        ),
        shadow="sm",
        padding="lg",
        radius="md",
        with_border=True,
    )


# ─── KPI grid ─────────────────────────────────────────────────────────────────


def _kpi_grid() -> rx.Component:
    """Responsive grid of stat cards."""
    return mn.simple_grid(
        stat_card("Einträge", MyFeatureState.total_count, "list", "blue"),
        stat_card("Aktiv",    MyFeatureState.active_count, "check-circle", "green"),
        stat_card("Ausstehend", MyFeatureState.pending_count, "clock", "orange"),
        cols={"base": 1, "sm": 3},
        spacing="md",
        w="100%",
    )


# ─── Tabs ─────────────────────────────────────────────────────────────────────


def feature_tabs() -> rx.Component:
    """Tabbed layout. Tab selection persisted via LocalStorage in state."""
    return mn.tabs(
        mn.tabs.list(
            mn.tabs.tab("Übersicht", value="overview"),
            mn.tabs.tab("Analyse",   value="analysis"),
        ),
        mn.tabs.panel(
            overview_content(),
            value="overview",
            pt="md",
        ),
        mn.tabs.panel(
            analysis_content(),
            value="analysis",
            pt="md",
        ),
        value=MyFeatureState.selected_tab,
        on_change=MyFeatureState.set_selected_tab,
    )


# ─── Top-level page content ───────────────────────────────────────────────────


def overview_content() -> rx.Component:
    return mn.stack(
        _kpi_grid(),
        _filter_bar(),
        rx.cond(
            MyFeatureState.is_loading,
            mn.center(mn.loader(size="lg"), h=300),
            rx.cond(
                MyFeatureState.items,
                _items_table(),
                _empty_state(),
            ),
        ),
        gap="md",
        w="100%",
    )


def analysis_content() -> rx.Component:
    return mn.stack(
        monthly_bar_chart(),
        gap="md",
        w="100%",
    )


def my_feature_page_content() -> rx.Component:
    """Root component for the feature page. Import this in pages.py."""
    return mn.stack(
        feature_tabs(),
        gap="md",
        w="100%",
    )

# ─── Component rendering rules ───────────────────────────────────────────────────

NEVER use bare Python if inside component functions. Use rx.cond and rx.foreach.

```python
# CORRECT
def item_list() -> rx.Component:
    return mn.stack(
        rx.cond(
            ListState.is_empty,
            mn.text("No items"),
            rx.foreach(ListState.items, render_item),
        ),
    )

# WRONG — won't react to state changes
def item_list() -> rx.Component:
    if ListState.is_empty:  # Static evaluation at import time!
        return mn.text("No items")
    return mn.stack(...)
```
