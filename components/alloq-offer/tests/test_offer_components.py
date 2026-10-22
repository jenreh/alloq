"""Render tests of the offer components."""

from alloq_commons.access import NO_ACCESS_MSG
from alloq_commons.roles import OFFER_EDITOR_ROLE
from alloq_offer.components import offer_modal, offer_parts, offer_table
from alloq_offer.components.offer_inspector import offer_inspector
from alloq_offer.components.offer_toolbar import (
    SEARCH_PLACEHOLDER,
    offer_filter,
    offer_toolbar,
)
from alloq_offer.pages import create_offers_page, offers_content


def test_table_renders_groups_and_columns() -> None:
    rendered = str(offer_table.offer_table())
    for _title, rows in offer_table.GROUPS:
        assert rows in rendered
    assert offer_table.TEMPLATE in rendered
    assert next(c[1] for c in offer_table.COLUMNS) == "title"


def test_table_empty_texts_are_constants() -> None:
    assert offer_parts.EMPTY_FILTERED != offer_parts.EMPTY_ALL
    assert offer_parts.EMPTY_FILTERED_HINT != offer_parts.EMPTY_ALL_HINT


def test_filtered_empty_state_offers_reset_and_hides_total() -> None:
    rendered = str(offer_table.offer_list())
    assert offer_parts.EMPTY_FILTERED_HINT in rendered
    assert "reset_filters" in rendered
    assert "aq-offer-empty" in rendered
    # The sum row is the else branch of the empty check, so it hides with no rows.
    empty_check = rendered.index("row_count")
    assert empty_check < rendered.index("aq-offer-empty") < rendered.index("aq-tfoot")


def test_empty_state_offers_create_button() -> None:
    rendered = str(offer_table.offer_table())
    assert offer_parts.EMPTY_ALL_HINT in rendered
    assert "open_create_modal" in rendered


def test_inspector_renders() -> None:
    rendered = str(offer_inspector())
    assert "inspected_margin" in rendered
    assert "industry" in rendered
    assert "update_inspected_state" in rendered


def test_inspector_without_selection_shows_empty_state() -> None:
    rendered = str(offer_inspector())
    assert "LucideMousePointerClick" in rendered
    assert offer_parts.NO_SELECTION_HINT != offer_parts.NO_SELECTION


def test_modal_has_all_fields() -> None:
    rendered = str(offer_modal.offer_modal())
    for name in (
        "title",
        "customer",
        "key_accounter",
        "industry_id",
        "person_days",
        "risk_buffer_days",
        "production_cost",
        "recommended_price",
        "sharepoint_url",
        "state",
    ):
        assert f'name:"{name}"' in rendered.replace(" ", "")
    assert "industry_options" in rendered


def test_toolbar() -> None:
    assert len(offer_toolbar()) == 3
    assert "list_filter" in str(offer_filter())
    assert SEARCH_PLACEHOLDER == "Angebot, Kunde oder Account Manager"


def test_state_tones_cover_all_states() -> None:
    assert set(offer_parts.STATE_TONES) == set(offer_modal.STATE_OPTIONS)


def test_page_factory() -> None:
    assert callable(create_offers_page(offer_parts.state_badge))  # type: ignore[arg-type]


def test_page_content_is_readable_by_everyone() -> None:
    assert NO_ACCESS_MSG.split(",")[0] not in str(offers_content())


def test_only_offer_editors_get_the_edit_modal() -> None:
    modal = str(offers_content().children[0])
    assert OFFER_EDITOR_ROLE.name in modal
    assert "Angebot speichern" in modal


def test_edit_controls_need_the_offer_editor_role() -> None:
    for part in (offer_inspector(), offer_toolbar()[-1], offer_table._no_offers()):
        assert f'"{OFFER_EDITOR_ROLE.name}"' in str(part)


def test_labels_avoid_company_abbreviations() -> None:
    labels = {label for label, _field, _numeric in offer_table.COLUMNS}
    assert {"Account Manager", "Branche", "Kosten", "Preis"} <= labels
    assert not labels & {"CIU", "Key Accounter", "HK", "VK", "PT"}
