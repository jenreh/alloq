"""Admin spreadsheet drafts, recalculation and explicit document saves."""

import logging
from collections.abc import AsyncGenerator
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import reflex as rx
from alloq_commons.models.price_list import PriceGridRow, PriceList, PricePosition
from alloq_commons.repositories import role_repo
from alloq_commons.repositories.price_list_repository import (
    PriceListConflict,
    price_list_repo,
)
from alloq_commons.services.price_list_pricing import (
    CENT,
    calculate_position,
    format_money,
    parse_money,
)
from alloq_commons.services.price_list_templates import price_list_template
from pydantic import ValidationError

from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.decorators import requires_admin

logger = logging.getLogger(__name__)
SETTINGS = {
    "name",
    "as_of",
    "hours_per_day",
    "minimum_margin",
    "target_margin",
    "cost_basis",
}
MONEY_COLUMNS = (
    "hourly_cost",
    "daily_cost",
    "minimum_daily",
    "minimum_hourly",
    "sales_price",
    "hourly_sales",
)


def grid_rows(sheet: PriceList) -> list[PriceGridRow]:
    rows = []
    for position in sheet.positions:
        priced = calculate_position(position, sheet)
        amounts = {
            "hourly_cost": priced.hourly_cost,
            "daily_cost": priced.daily_cost,
            "minimum_daily": priced.minimum_daily,
            "minimum_hourly": priced.minimum_hourly,
            "sales_price": priced.daily_sales,
            "hourly_sales": priced.hourly_sales,
        }
        values = {"la": position.la, "label": position.label}
        values.update(
            {
                key: f"{value.quantize(CENT, rounding=ROUND_HALF_UP):.2f}"
                if value is not None
                else ""
                for key, value in amounts.items()
            }
        )
        display = {"la": position.la, "label": position.label}
        display.update({key: format_money(value) for key, value in amounts.items()})
        effective_sales = values["sales_price"]
        values["sales_price"] = (
            f"{position.sales_price:.2f}" if position.sales_price is not None else ""
        )
        rows.append(
            PriceGridRow(
                key=position.key,
                role_id=str(position.role_id or ""),
                cell_values=values,
                display=display,
                below_minimum=priced.below_minimum,
                effective_sales=effective_sales,
            )
        )
    return rows


class PriceListState(rx.State):
    lists: rx.Field[list[PriceList]] = rx.field(default_factory=list)
    draft: rx.Field[PriceList] = rx.field(
        default_factory=lambda: PriceList(name="Neue Preisliste")
    )
    role_options: rx.Field[list[dict[str, str]]] = rx.field(default_factory=list)
    selected_id: rx.Field[str] = rx.field("")
    compare_id: rx.Field[str] = rx.field("")
    show_archived: rx.Field[bool] = rx.field(False)
    show_hourly: rx.Field[bool] = rx.field(True)
    show_roles: rx.Field[bool] = rx.field(True)
    is_loading: rx.Field[bool] = rx.field(False)
    is_saving: rx.Field[bool] = rx.field(False)
    grid_revision: rx.Field[int] = rx.field(0)
    settings_revision: rx.Field[int] = rx.field(0)
    pending_action: rx.Field[str] = rx.field("")
    pending_value: rx.Field[str] = rx.field("")
    template_key: rx.Field[str] = rx.field("2026")
    error_message: rx.Field[str] = rx.field("")
    _baseline: dict[str, Any] = {}
    _saved: PriceList = PriceList(name="Neue Preisliste")

    @rx.var
    def has_dirty(self) -> bool:
        return self.draft.model_dump(mode="json") != self._baseline

    @rx.var
    def list_options(self) -> list[dict[str, str]]:
        return [
            {
                "value": str(item.id),
                "label": item.name + (" (archiviert)" if item.archived else ""),
            }
            for item in self.lists
            if self.show_archived or not item.archived or item.id == self.draft.id
        ]

    @rx.var
    def rows(self) -> list[PriceGridRow]:
        return grid_rows(self.draft)

    @rx.var
    def compare_rows(self) -> list[PriceGridRow]:
        return grid_rows(
            next(
                (item for item in self.lists if str(item.id) == self.compare_id),
                PriceList(name="Vergleich"),
            )
        )

    @rx.var
    def compare_name(self) -> str:
        return next(
            (item.name for item in self.lists if str(item.id) == self.compare_id), ""
        )

    @rx.var
    def compare_cost_basis(self) -> str:
        return next(
            (item.cost_basis for item in self.lists if str(item.id) == self.compare_id),
            "day",
        )

    @rx.var
    def hourly_visible(self) -> bool:
        return self.show_hourly or self.draft.cost_basis == "hour"

    @rx.var
    def cost_basis(self) -> str:
        return self.draft.cost_basis

    @rx.var
    def is_archived(self) -> bool:
        return self.draft.archived

    @rx.var
    def settings_values(self) -> dict[str, str]:
        return {
            "name": self.draft.name,
            "as_of": str(self.draft.as_of or ""),
            "hours_per_day": format(self.draft.hours_per_day.normalize(), "f").replace(
                ".", ","
            ),
            "minimum_margin": format(
                self.draft.minimum_margin.normalize(), "f"
            ).replace(".", ","),
            "target_margin": format(self.draft.target_margin.normalize(), "f").replace(
                ".", ","
            )
            if self.draft.target_margin is not None
            else "",
        }

    def _accept(self, sheet: PriceList) -> None:
        self.draft = sheet.model_copy(deep=True)
        self._saved = sheet.model_copy(deep=True)
        self._baseline = sheet.model_dump(mode="json")
        self.selected_id = str(sheet.id) if sheet.id else ""
        self.grid_revision += 1
        self.settings_revision += 1
        self.error_message = ""

    async def _refresh_lists(self) -> None:
        async with get_asyncdb_session() as session:
            self.lists = await price_list_repo.list_all(session)
            roles = await role_repo.find_all_paginated(session)
            self.role_options = [
                {"value": str(role.id), "label": role.name} for role in roles
            ]

    @rx.event
    @requires_admin
    async def load(self) -> AsyncGenerator[Any]:
        self.is_loading = True
        yield
        try:
            await self._refresh_lists()
            if not self._baseline:
                self._accept(
                    next(
                        (item for item in self.lists if not item.archived),
                        PriceList(name="Neue Preisliste"),
                    )
                )
        except Exception:
            logger.exception("Failed to load price lists")
            self.error_message = "Fehler beim Laden der Preislisten."
            yield rx.toast.error(self.error_message)
        finally:
            self.is_loading = False

    @rx.event
    @requires_admin
    async def set_view(self, field: str, value: bool) -> None:
        if field in {
            "show_archived",
            "show_hourly",
            "show_roles",
        }:
            setattr(self, field, value)

    @rx.event
    @requires_admin
    async def set_template(self, value: str) -> None:
        if value in {"germany", "2025", "2026"}:
            self.template_key = value

    @rx.event
    @requires_admin
    async def set_compare(self, value: str) -> None:
        self.compare_id = (
            value if any(str(item.id) == value for item in self.lists) else ""
        )

    @rx.event
    @requires_admin
    async def set_setting(self, field: str, value: str) -> AsyncGenerator[Any]:
        if field not in SETTINGS:
            return
        document = self.draft.model_dump()
        try:
            parsed: Any = value
            if field in {"hours_per_day", "minimum_margin", "target_margin"}:
                parsed = Decimal(value.replace(",", ".")) if value else None
            elif field == "as_of":
                parsed = date.fromisoformat(value) if value else None
            document[field] = parsed
            new = PriceList.model_validate(document)
            if field == "cost_basis" and value != self.draft.cost_basis:
                for position, old in zip(
                    new.positions, self.draft.positions, strict=True
                ):
                    priced = calculate_position(old, self.draft)
                    cost = priced.hourly_cost if value == "hour" else priced.daily_cost
                    position.cost = (
                        cost.quantize(CENT, rounding=ROUND_HALF_UP)
                        if cost is not None
                        else None
                    )
                new = PriceList.model_validate(new.model_dump())
                self.grid_revision += 1
            self.draft = new
        except ValueError, ArithmeticError:
            self.settings_revision += 1
            yield rx.toast.error(
                "Ungültige Einstellung. Name, Datum und Zahlen prüfen."
            )

    @rx.event
    @requires_admin
    async def apply_cell_changes(
        self, changes: list[dict[str, Any]]
    ) -> AsyncGenerator[Any]:
        draft = self.draft.model_copy(deep=True)
        by_key = {position.key: position for position in draft.positions}
        rejected = 0
        cost_column = "hourly_cost" if draft.cost_basis == "hour" else "daily_cost"
        for change in changes:
            try:
                key, column = str(change["key"]).rsplit("|", 1)
                row = by_key.get(key)
                if row is None or column not in {
                    "la",
                    "label",
                    cost_column,
                    "sales_price",
                }:
                    continue
                field = "cost" if column == cost_column else column
                value = (
                    parse_money(change.get("value"))
                    if field in {"cost", "sales_price"}
                    else str(change.get("value", ""))
                )
                replacement = PricePosition.model_validate(
                    {**row.model_dump(), field: value}
                )
                draft.positions[draft.positions.index(row)] = replacement
                by_key[key] = replacement
            except ValueError, KeyError, TypeError:
                rejected += 1
        self.draft = draft
        if rejected:
            yield rx.toast.error(
                f"Ungültige Eingaben: {rejected}. Preise: 0,01 bis 100.000 €."
            )

    @rx.event
    @requires_admin
    async def notify_rejected(self, count: int) -> AsyncGenerator[Any]:
        yield rx.toast.error(f"Ungültige Eingaben übersprungen: {count}.")

    @rx.event
    @requires_admin
    async def add_row(self) -> None:
        new = self.draft.model_copy(deep=True)
        new.positions.append(PricePosition())
        self.draft = new

    @rx.event
    @requires_admin
    async def delete_row(self, key: str) -> None:
        new = self.draft.model_copy(deep=True)
        new.positions = [row for row in new.positions if row.key != key]
        self.draft = new
        self.grid_revision += 1

    @rx.event
    @requires_admin
    async def move_row(self, key: str, delta: int) -> None:
        new = self.draft.model_copy(deep=True)
        index = next((i for i, row in enumerate(new.positions) if row.key == key), -1)
        target = index + delta
        if index >= 0 and delta in {-1, 1} and 0 <= target < len(new.positions):
            new.positions[index], new.positions[target] = (
                new.positions[target],
                new.positions[index],
            )
            self.draft = new

    @rx.event
    @requires_admin
    async def set_role(self, key: str, value: str) -> None:
        if value and value not in {option["value"] for option in self.role_options}:
            return
        new = self.draft.model_copy(deep=True)
        for position in new.positions:
            if position.key == key:
                position.role_id = int(value) if value else None
        self.draft = new

    @rx.event
    @requires_admin
    async def toggle_archive(self) -> None:
        self.draft = self.draft.model_copy(update={"archived": not self.draft.archived})

    @rx.event
    @requires_admin
    async def discard(self) -> None:
        self._accept(self._saved)

    @rx.event
    @requires_admin
    async def save(self) -> AsyncGenerator[Any]:
        try:
            validated = PriceList.model_validate(self.draft.model_dump())
            for position in validated.positions:
                position.validate_identity()
        except ValidationError:
            yield rx.toast.error(
                "Jede Zeile benötigt LA oder Rolle; bitte Eingaben prüfen."
            )
            return
        self.is_saving = True
        yield
        try:
            async with get_asyncdb_session() as session:
                saved = await price_list_repo.save_document(session, validated)
            self._accept(saved)
            self.lists = sorted(
                [item for item in self.lists if item.id != saved.id] + [saved],
                key=lambda item: (item.archived, item.name, item.id),
            )
            yield rx.toast.success("Preisliste gespeichert.")
        except PriceListConflict:
            self.error_message = (
                "Die Preisliste wurde zwischenzeitlich geändert. "
                "Entwurf bleibt erhalten. Bitte neu laden oder als Kopie speichern."
            )
            yield rx.toast.error(self.error_message)
        except Exception:
            logger.exception("Failed to save price list")
            self.error_message = "Fehler beim Speichern. Der Entwurf bleibt erhalten."
            yield rx.toast.error(self.error_message)
        finally:
            self.is_saving = False

    async def _perform(self, action: str, value: str) -> None:
        if action == "select":
            async with get_asyncdb_session() as session:
                sheet = await price_list_repo.load(session, int(value))
            self._accept(sheet)
        elif action == "reload":
            sheet_id = self.draft.id or self._saved.id
            if sheet_id:
                async with get_asyncdb_session() as session:
                    sheet = await price_list_repo.load(session, sheet_id)
                self._accept(sheet)
            else:
                self._accept(self._saved)
            await self._refresh_lists()
        else:
            sheet = (
                self.draft.duplicate()
                if action == "duplicate"
                else price_list_template(value)
                if action == "template"
                else PriceList(name="Neue Preisliste")
            )
            previous = self._saved
            self._accept(sheet)
            self._saved = previous
            self._baseline = {}

    @rx.event
    @requires_admin
    async def request_action(self, action: str, value: str) -> AsyncGenerator[Any]:
        if action not in {"select", "new", "duplicate", "template", "reload"}:
            return
        if action == "select" and value == self.selected_id:
            return
        if self.has_dirty and action != "duplicate":
            self.pending_action, self.pending_value = action, value
            return
        try:
            await self._perform(action, value)
        except ValueError, PriceListConflict:
            yield rx.toast.error("Preisliste nicht verfügbar.")
        except Exception:
            logger.exception("Failed to switch price list")
            yield rx.toast.error("Fehler beim Laden der Preisliste.")

    @rx.event
    @requires_admin
    async def resolve_pending(self, resolution: str) -> AsyncGenerator[Any]:
        action, value = self.pending_action, self.pending_value
        if resolution == "stay":
            self.pending_action = self.pending_value = ""
            return
        if resolution == "save":
            async for event in self.save():
                yield event
            if self.has_dirty:
                return
        if action and resolution in {"save", "discard"}:
            try:
                await self._perform(action, value)
                self.pending_action = self.pending_value = ""
            except Exception:
                logger.exception("Failed to resolve price list switch")
                yield rx.toast.error("Fehler beim Wechseln der Preisliste.")
