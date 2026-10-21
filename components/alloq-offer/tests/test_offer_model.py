"""Tests for the offer entity and write model."""

from decimal import Decimal
from typing import Any

import pytest
from alloq_offer.entities import (
    CIU_LABELS,
    CustomerIndustryUnit,
    OfferEntity,
    OfferStateEnum,
)
from alloq_offer.models import Offer, OfferCreate
from pydantic import ValidationError


def _valid(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "title": "Relaunch",
        "customer": "ACME",
        "person_days": "10",
        "risk_buffer_days": "2",
        "production_cost": "5000",
        "recommended_price": "8000",
        "key_accounter": "Max Muster",
        "ciu": "FS",
    }
    return data | overrides


class TestOfferEntity:
    def test_to_dict_has_all_keys(self) -> None:
        entity = OfferEntity(
            id=1,
            title="T",
            customer="C",
            person_days=Decimal(1),
            risk_buffer_days=Decimal(0),
            production_cost=Decimal(2),
            recommended_price=Decimal(3),
            key_accounter="K",
            ciu="CP",
            state=OfferStateEnum.NEW,
            archived=False,
        )
        data = entity.to_dict()
        assert set(data) == {
            "id",
            "title",
            "customer",
            "person_days",
            "risk_buffer_days",
            "production_cost",
            "recommended_price",
            "key_accounter",
            "ciu",
            "sharepoint_url",
            "sent_date",
            "state",
            "archived",
            "created",
            "updated",
        }
        assert Offer(**data).title == "T"

    def test_tablename(self) -> None:
        assert OfferEntity.__tablename__ == "offers"

    def test_ciu_labels_cover_every_code(self) -> None:
        assert set(CIU_LABELS) == {c.value for c in CustomerIndustryUnit}
        assert CIU_LABELS["IMC"] == "Industrial Midcaps - IMC"


class TestOfferCreate:
    def test_valid_defaults(self) -> None:
        offer = OfferCreate(**_valid())
        assert offer.state == OfferStateEnum.NEW
        assert offer.sharepoint_url is None
        assert offer.sent_date is None

    def test_strips_text(self) -> None:
        assert OfferCreate(**_valid(title="  Hi  ")).title == "Hi"

    @pytest.mark.parametrize("field", ["title", "customer", "key_accounter"])
    @pytest.mark.parametrize("value", ["", "   "])
    def test_rejects_empty_text(self, field: str, value: str) -> None:
        with pytest.raises(ValidationError):
            OfferCreate(**_valid(**{field: value}))

    @pytest.mark.parametrize(
        "field",
        ["person_days", "risk_buffer_days", "production_cost", "recommended_price"],
    )
    def test_rejects_negative_numbers(self, field: str) -> None:
        with pytest.raises(ValidationError):
            OfferCreate(**_valid(**{field: "-1"}))

    def test_rejects_unknown_ciu_and_state(self) -> None:
        with pytest.raises(ValidationError):
            OfferCreate(**_valid(ciu="XX"))
        with pytest.raises(ValidationError):
            OfferCreate(**_valid(state="Offen"))

    def test_sharepoint_url_rules(self) -> None:
        assert OfferCreate(**_valid(sharepoint_url="")).sharepoint_url is None
        ok = OfferCreate(**_valid(sharepoint_url=" https://x.sharepoint.com/a "))
        assert ok.sharepoint_url == "https://x.sharepoint.com/a"
        with pytest.raises(ValidationError):
            OfferCreate(**_valid(sharepoint_url="ftp://x"))
        with pytest.raises(ValidationError):
            OfferCreate(**_valid(sharepoint_url="javascript:alert(1)"))
