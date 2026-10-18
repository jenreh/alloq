"""Keeps the documented database schema in sync with the SQLAlchemy metadata.

``doc/database/schema.erd.json`` is the source of the rendered ERD in
``doc/database/schema.html``. When a test here fails, update the JSON (the
failure lists the expected columns) and re-render the HTML.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import alloq_commons.entities  # noqa: F401  (registers tables on Base.metadata)
import pytest
from sqlalchemy import Column, Index, Table, UniqueConstraint
from sqlalchemy.dialects import postgresql

import appkit_user.authentication.backend.database.entities  # noqa: F401
from appkit_commons.database.entities import Base

DOC_DIR = Path(__file__).resolve().parents[1] / "doc" / "database"
ERD = DOC_DIR / "schema.erd.json"
HTML = DOC_DIR / "schema.html"
# Written by archify next to the HTML; pins the JSON it was rendered from.
RECEIPT = DOC_DIR / "schema.delivery.json"

_DIALECT = postgresql.dialect()
_TYPE_ALIASES = {
    "timestamp with time zone": "timestamptz",
    "timestamp without time zone": "timestamp",
}


def _sql_type(column: Column) -> str:
    """PostgreSQL type of *column*, suffixed with ``null`` when nullable."""
    if "Encrypted" in type(column.type).__name__:
        sql = "encrypted varchar"
    else:
        sql = column.type.compile(dialect=_DIALECT).lower()
    sql = _TYPE_ALIASES.get(sql, sql)
    return f"{sql} null" if column.nullable else sql


def _is_unique(table: Table, column: Column) -> bool:
    if column.unique:
        return True
    single = [column.name]
    if any(
        isinstance(c, UniqueConstraint) and [col.name for col in c.columns] == single
        for c in table.constraints
    ):
        return True
    return any(
        isinstance(i, Index) and i.unique and [col.name for col in i.columns] == single
        for i in table.indexes
    )


def _expected_attribute(table: Table, column: Column) -> dict[str, Any]:
    keys = []
    if column.primary_key:
        keys.append("pk")
    if column.foreign_keys:
        keys.append("fk")
    if _is_unique(table, column):
        keys.append("uk")
    attribute: dict[str, Any] = {"name": column.name, "type": _sql_type(column)}
    if keys:
        attribute["key"] = keys
    if column.foreign_keys:
        attribute["references"] = next(iter(column.foreign_keys)).target_fullname
    return attribute


def _documented_attribute(attribute: dict[str, Any]) -> dict[str, Any]:
    """Normalise a documented attribute (``key`` may be a string or a list)."""
    normalised = dict(attribute)
    if isinstance(normalised.get("key"), str):
        normalised["key"] = [normalised["key"]]
    return normalised


def _by_name(attributes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {a["name"]: a for a in attributes}


@pytest.fixture(scope="module")
def erd() -> dict[str, Any]:
    return json.loads(ERD.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def entities(erd: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {e["id"]: e for e in erd["entities"]}


def test_every_table_is_documented(entities: dict[str, dict[str, Any]]) -> None:
    assert set(entities) == set(Base.metadata.tables)


@pytest.mark.parametrize("table_name", sorted(Base.metadata.tables))
def test_table_columns_match(
    table_name: str, entities: dict[str, dict[str, Any]]
) -> None:
    table = Base.metadata.tables[table_name]
    expected = [_expected_attribute(table, c) for c in table.columns]
    documented = [
        _documented_attribute(a)
        for a in entities.get(table_name, {}).get("attributes", [])
    ]
    assert _by_name(documented) == _by_name(expected), (
        f"Update {table_name} in {ERD.name} to:\n{json.dumps(expected, indent=2)}"
    )


def test_relationships_match_foreign_keys(erd: dict[str, Any]) -> None:
    """One relationship per foreign key, labelled with its ON DELETE action.

    The renderer cannot draw self-references; they are described in a card.
    """
    expected = {
        (
            table.name,
            fk.column.table.name,
            fk.parent.nullable,
            (fk.ondelete or "").lower(),
        )
        for table in Base.metadata.tables.values()
        for fk in table.foreign_keys
        if fk.column.table is not table
    }
    documented = {
        (r["from"], r["to"], r.get("toOptional", False), r.get("label", ""))
        for r in erd.get("relationships", [])
    }
    assert documented == expected


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_html_is_rendered_from_current_json() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["specification"]["sha256"] == _sha256(ERD), (
        f"{HTML.name} is stale: re-render it from {ERD.name}"
    )
    assert receipt["artifact"]["sha256"] == _sha256(HTML)
