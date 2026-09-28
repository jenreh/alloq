"""Tests for hand-written Alembic data migrations (run offline on SQLite)."""

import importlib.util
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic.migration import MigrationContext
from alembic.operations import Operations

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"

# Days after Easter Sunday for NRW's moveable holidays.
EASTER_OFFSETS = {
    "Karfreitag": -2,
    "Ostersonntag": 0,
    "Ostermontag": 1,
    "Christi Himmelfahrt": 39,
    "Pfingstsonntag": 49,
    "Pfingstmontag": 50,
    "Fronleichnam": 60,
}


def _easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _load(filename: str) -> ModuleType:
    path = VERSIONS / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def seed_rows() -> list[dict]:
    """Rows the public_holidays migration bulk-inserts."""
    seed = _load("2026_05_11_public_holidays.py")
    fake_op = MagicMock()
    with patch.object(seed, "op", fake_op):
        seed.upgrade()
    return fake_op.bulk_insert.call_args.args[1]


@pytest.fixture(scope="module")
def fix() -> ModuleType:
    return _load("2026_09_28_fix_holiday_dates_and_default_admin.py")


@pytest.fixture
def connection(seed_rows: list[dict]) -> Iterator[Connection]:
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    holidays = sa.Table(
        "public_holidays",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String),
        sa.Column("date", sa.Date),
        sa.Column("is_recurring", sa.Boolean),
        sa.Column("state_code", sa.String),
    )
    sa.Table(
        "auth_users",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String),
        sa.Column("_password", sa.String),
        sa.Column("needs_password_reset", sa.Boolean),
    )
    with engine.begin() as conn:
        metadata.create_all(conn)
        conn.execute(holidays.insert(), seed_rows)
        yield conn


def _run(module: ModuleType, step: str, conn: Connection) -> None:
    operations = Operations(MigrationContext.configure(conn))
    with patch.object(module, "op", operations):
        getattr(module, step)()


def _holidays(conn: Connection) -> list[tuple[str, date]]:
    rows = conn.execute(sa.text("SELECT name, date FROM public_holidays"))
    return [(name, date.fromisoformat(str(day))) for name, day in rows]


def _moveable_mismatches(rows: list[tuple[str, date]]) -> list[tuple[str, date]]:
    return [
        (name, day)
        for name, day in rows
        if name in EASTER_OFFSETS
        and day != _easter(day.year) + timedelta(days=EASTER_OFFSETS[name])
    ]


def test_easter_algorithm() -> None:
    assert _easter(2026) == date(2026, 4, 5)
    assert _easter(2027) == date(2027, 3, 28)


def test_fix_targets_match_easter_offsets(fix: ModuleType) -> None:
    for name, _wrong, correct in fix.HOLIDAY_DATE_FIXES:
        expected = _easter(correct.year) + timedelta(days=EASTER_OFFSETS[name])
        assert correct == expected, name


def test_seed_plus_fix_matches_easter_offsets(
    fix: ModuleType, connection: Connection
) -> None:
    assert _moveable_mismatches(_holidays(connection))  # seed is wrong

    _run(fix, "upgrade", connection)

    rows = _holidays(connection)
    assert _moveable_mismatches(rows) == []
    assert len(rows) == len(set(rows))


def test_fix_drops_stale_row_when_correct_row_exists(
    fix: ModuleType, connection: Connection
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO public_holidays (name, date, is_recurring, state_code) "
            "VALUES ('Pfingstmontag', '2026-05-25', false, 'NRW')"
        )
    )

    _run(fix, "upgrade", connection)

    pfingstmontag = [row for row in _holidays(connection) if row[0] == "Pfingstmontag"]
    assert pfingstmontag.count(("Pfingstmontag", date(2026, 5, 25))) == 1
    assert ("Pfingstmontag", date(2026, 6, 25)) not in pfingstmontag


def test_downgrade_restores_seed_dates(fix: ModuleType, connection: Connection) -> None:
    before = sorted(_holidays(connection))

    _run(fix, "upgrade", connection)
    _run(fix, "downgrade", connection)

    assert sorted(_holidays(connection)) == before


def test_default_admin_hash_matches_baseline(fix: ModuleType) -> None:
    baseline = (VERSIONS / "2026_05_09_consolidated_baseline.py").read_text(
        encoding="utf-8"
    )

    assert f"'{fix.DEFAULT_ADMIN_PASSWORD_HASH}'" in baseline


def test_flags_default_admin_only_while_seeded_hash_is_unchanged(
    fix: ModuleType, connection: Connection
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO auth_users (email, _password, needs_password_reset) "
            "VALUES ('admin', :seeded, false), ('rotated', 'other-hash', false)"
        ),
        {"seeded": fix.DEFAULT_ADMIN_PASSWORD_HASH},
    )

    _run(fix, "upgrade", connection)

    rows = connection.execute(
        sa.text("SELECT email, needs_password_reset FROM auth_users")
    )
    flags = {email: bool(flag) for email, flag in rows}
    assert flags == {"admin": True, "rotated": False}


def test_revision_chain(fix: ModuleType) -> None:
    seed = _load("2026_05_11_public_holidays.py")

    assert fix.down_revision == seed.revision


# ---------------------------------------------------------------------------
# dd55ee66ff77 — absences date range CHECK + unique capacity assignment
# ---------------------------------------------------------------------------

CONSTRAINTS_FILE = "2026_09_28_absence_range_and_capacity_unique.py"


@pytest.fixture(scope="module")
def constraints() -> ModuleType:
    return _load(CONSTRAINTS_FILE)


@pytest.fixture
def planning_tables() -> Iterator[Connection]:
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "absences",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("employee_id", sa.Integer, nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
    )
    sa.Table(
        "capacities",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, nullable=False),
        sa.Column("employee_id", sa.Integer, nullable=False),
        sa.Column("role_id", sa.Integer, nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("hours_per_week", sa.Float, nullable=False),
    )
    with engine.begin() as conn:
        metadata.create_all(conn)
        yield conn


def _insert_absence(conn: Connection, start: str, end: str) -> None:
    conn.execute(
        sa.text(
            "INSERT INTO absences (employee_id, start_date, end_date) "
            "VALUES (1, :start, :end)"
        ),
        {"start": start, "end": end},
    )


def _insert_capacity(conn: Connection, start: str, end: str, hours: float) -> None:
    conn.execute(
        sa.text(
            "INSERT INTO capacities "
            "(project_id, employee_id, role_id, start_date, end_date, hours_per_week) "
            "VALUES (1, 2, 3, :start, :end, :hours)"
        ),
        {"start": start, "end": end, "hours": hours},
    )


def test_constraints_revision_follows_holiday_fix(
    constraints: ModuleType, fix: ModuleType
) -> None:
    assert constraints.down_revision == fix.revision


def test_upgrade_swaps_reversed_absences_and_enforces_range(
    constraints: ModuleType, planning_tables: Connection
) -> None:
    _insert_absence(planning_tables, "2026-05-10", "2026-05-04")

    _run(constraints, "upgrade", planning_tables)

    rows = planning_tables.execute(
        sa.text("SELECT start_date, end_date FROM absences")
    ).all()
    assert [(str(s), str(e)) for s, e in rows] == [("2026-05-04", "2026-05-10")]
    with pytest.raises(sa.exc.IntegrityError):
        _insert_absence(planning_tables, "2026-06-10", "2026-06-01")


def test_upgrade_merges_duplicate_capacities_and_enforces_uniqueness(
    constraints: ModuleType, planning_tables: Connection
) -> None:
    _insert_capacity(planning_tables, "2026-03-01", "2026-04-30", 40.0)
    _insert_capacity(planning_tables, "2026-01-01", "2026-03-31", 20.0)

    _run(constraints, "upgrade", planning_tables)

    rows = planning_tables.execute(
        sa.text("SELECT id, start_date, end_date, hours_per_week FROM capacities")
    ).all()
    assert [(i, str(s), str(e), h) for i, s, e, h in rows] == [
        (1, "2026-01-01", "2026-04-30", 40.0)
    ]
    with pytest.raises(sa.exc.IntegrityError):
        _insert_capacity(planning_tables, "2026-01-01", "2026-01-31", 40.0)


def test_downgrade_drops_constraints(
    constraints: ModuleType, planning_tables: Connection
) -> None:
    _run(constraints, "upgrade", planning_tables)
    _run(constraints, "downgrade", planning_tables)

    _insert_absence(planning_tables, "2026-06-10", "2026-06-01")
    _insert_capacity(planning_tables, "2026-01-01", "2026-01-31", 40.0)
    _insert_capacity(planning_tables, "2026-01-01", "2026-01-31", 40.0)
