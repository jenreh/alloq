"""Tests for the pure offer services."""

from datetime import date
from decimal import Decimal

import pytest
from alloq_offer.models import Offer
from alloq_offer.services.offers import (
    FILTER_ALL,
    FILTER_ARCHIVED,
    apply_state_change,
    can_accept,
    default_project_dates,
    filter_offers,
    group_offers,
    margin_pct,
    project_from_offer,
    search_offers,
    sort_offers,
    total_days,
    totals,
    visible_offers,
)

TODAY = date(2026, 10, 21)


def _offer(**kw: object) -> Offer:
    base: dict[str, object] = {
        "id": 1,
        "title": "Alpha",
        "customer": "ACME",
        "key_accounter": "Max",
        "person_days": Decimal(10),
        "risk_buffer_days": Decimal(2),
        "production_cost": Decimal(600),
        "recommended_price": Decimal(1000),
        "ciu": "FS",
        "state": "Neu",
    }
    return Offer(**(base | kw))


class TestApplyStateChange:
    def test_sets_today_when_sent_without_date(self) -> None:
        assert apply_state_change("Neu", None, "Versendet", TODAY) == TODAY

    def test_keeps_existing_date_when_sent(self) -> None:
        old = date(2026, 1, 1)
        assert apply_state_change("Neu", old, "Versendet", TODAY) == old

    def test_keeps_date_when_moving_back(self) -> None:
        old = date(2026, 1, 1)
        assert apply_state_change("Versendet", old, "Neu", TODAY) == old

    def test_no_date_for_other_states(self) -> None:
        assert apply_state_change("Neu", None, "In Bearbeitung", TODAY) is None


class TestDerived:
    def test_total_days(self) -> None:
        assert total_days(_offer()) == Decimal(12)

    def test_margin(self) -> None:
        assert margin_pct(_offer()) == Decimal(40)

    def test_margin_none_without_price(self) -> None:
        assert margin_pct(_offer(recommended_price=Decimal(0))) is None

    def test_totals(self) -> None:
        result = totals([_offer(), _offer(id=2)])
        assert result.person_days == Decimal(24)
        assert result.production_cost == Decimal(1200)
        assert result.recommended_price == Decimal(2000)

    def test_totals_empty(self) -> None:
        assert totals([]).person_days == 0


class TestSearchAndFilter:
    def setup_method(self) -> None:
        self.offers = [
            _offer(id=1, title="Alpha", customer="ACME", key_accounter="Max"),
            _offer(id=2, title="Beta", customer="Globex", key_accounter="Eva"),
            _offer(id=3, title="Gamma", state="Versendet", archived=True),
        ]

    @pytest.mark.parametrize(
        ("query", "ids"),
        [("", [1, 2, 3]), ("alp", [1]), ("GLOBEX", [2]), ("eva", [2]), ("zzz", [])],
    )
    def test_search(self, query: str, ids: list[int]) -> None:
        assert [o.id for o in search_offers(self.offers, query)] == ids

    def test_filter_all_hides_archived(self) -> None:
        assert [o.id for o in filter_offers(self.offers, FILTER_ALL)] == [1, 2]

    def test_filter_state(self) -> None:
        assert filter_offers(self.offers, "Versendet") == []
        assert [o.id for o in filter_offers(self.offers, "Neu")] == [1, 2]

    def test_filter_archived(self) -> None:
        assert [o.id for o in filter_offers(self.offers, FILTER_ARCHIVED)] == [3]


class TestSortAndGroup:
    def setup_method(self) -> None:
        self.offers = [
            _offer(id=1, title="b", sent_date=date(2026, 5, 1)),
            _offer(id=2, title="A", person_days=Decimal(1), state="Versendet"),
            _offer(id=3, title="c", sent_date=date(2026, 6, 1), state="In Bearbeitung"),
        ]

    def test_sort_title_case_insensitive(self) -> None:
        assert [o.id for o in sort_offers(self.offers, "title", desc=False)] == [
            2,
            1,
            3,
        ]
        assert [o.id for o in sort_offers(self.offers, "title", desc=True)] == [3, 1, 2]

    def test_sort_numbers_use_total_days(self) -> None:
        assert sort_offers(self.offers, "person_days", desc=False)[0].id == 2

    def test_sort_state_follows_group_order(self) -> None:
        assert [o.id for o in sort_offers(self.offers, "state", desc=False)] == [
            1,
            3,
            2,
        ]

    def test_sent_date_puts_empty_last(self) -> None:
        assert [o.id for o in sort_offers(self.offers, "sent_date", desc=False)] == [
            1,
            3,
            2,
        ]
        assert [o.id for o in sort_offers(self.offers, "sent_date", desc=True)] == [
            3,
            1,
            2,
        ]

    def test_unknown_column_keeps_order(self) -> None:
        assert [o.id for o in sort_offers(self.offers, "nope", desc=False)] == [1, 2, 3]

    def test_group(self) -> None:
        groups = group_offers(self.offers)
        assert list(groups) == ["Neu", "In Bearbeitung", "Versendet"]
        assert [o.id for o in groups["Versendet"]] == [2]

    def test_visible_offers_combines_all(self) -> None:
        result = visible_offers(
            self.offers,
            query="",
            list_filter="Alle",
            sort_column="title",
            sort_desc=True,
        )
        assert [o.id for o in result] == [3, 1, 2]


class TestAcceptance:
    def test_can_accept_only_open_unarchived_offers(self) -> None:
        assert can_accept(_offer())
        assert not can_accept(_offer(archived=True))
        assert not can_accept(_offer(project_id=5))

    def test_default_dates_span_the_placeholder_duration(self) -> None:
        start, end = default_project_dates(TODAY)
        assert start == TODAY
        assert (end - start).days == 90

    def test_project_takes_over_offer_data(self) -> None:
        project = project_from_offer(
            _offer(recommended_price=Decimal("1234.60")),
            "ABC",
            date(2026, 11, 1),
            date(2026, 12, 1),
        )
        assert project.code == "ABC"
        assert project.name_de == "Alpha"
        assert project.customer == "ACME"
        assert project.budget == 1235
        assert project.state == "Geplant"
        assert (project.start_date, project.end_date) == (
            date(2026, 11, 1),
            date(2026, 12, 1),
        )
