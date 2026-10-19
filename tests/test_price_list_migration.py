"""Legacy rate migration preserves inputs and has a reversible schema."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import sqlalchemy as sa

from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_price_list_upgrade_and_downgrade() -> None:
    filename = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/2026_10_19_price_lists.py"
    )
    spec = importlib.util.spec_from_file_location("price_list_migration", filename)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE roles (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(
            sa.text("INSERT INTO roles VALUES (1, 'Data Scientist'), (2, 'Extern')")
        )
        conn.execute(
            sa.text(
                "CREATE TABLE daily_rates (id INTEGER PRIMARY KEY, role_id INTEGER, "
                "production_cost INTEGER, list_price INTEGER)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO daily_rates VALUES (1, 1, 710, NULL), (2, 2, NULL, 1600)"
            )
        )
        conn.execute(
            sa.text(
                "CREATE TABLE daily_rate_settings (id INTEGER PRIMARY KEY, "
                "min_contribution_margin_percent INTEGER, "
                "contribution_margin_percent INTEGER)"
            )
        )
        conn.execute(sa.text("INSERT INTO daily_rate_settings VALUES (1, 25, 40)"))
        with patch.object(module, "op", Operations(MigrationContext.configure(conn))):
            module.upgrade()
            header = conn.execute(
                sa.text(
                    "SELECT name, hours_per_day, minimum_margin, target_margin, "
                    "version FROM price_lists"
                )
            ).one()
            assert tuple(header) == ("Bestand", 8, 25, 40, 1)
            positions = conn.execute(
                sa.text(
                    "SELECT role_id, label, cost, sales_price, sort_order "
                    "FROM price_positions ORDER BY sort_order"
                )
            ).all()
            assert [tuple(row) for row in positions] == [
                (1, "Data Scientist", 710, None, 0),
                (2, "Extern", None, 1600, 1),
            ]
            module.downgrade()
            assert "price_lists" not in sa.inspect(conn).get_table_names()
            assert (
                conn.execute(sa.text("SELECT COUNT(*) FROM daily_rates")).scalar_one()
                == 2
            )
