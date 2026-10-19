"""Add independent price lists and copy legacy rates without changing inputs.

Revision ID: bc90de12fa34
Revises: ab89cd01ef23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "bc90de12fa34"
down_revision: str | None = "ab89cd01ef23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            name,
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )
        for name in ("created", "updated")
    ]


def upgrade() -> None:
    op.create_table(
        "price_lists",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=True),
        sa.Column("cost_basis", sa.String(4), nullable=False),
        sa.Column("hours_per_day", sa.Numeric(4, 2), nullable=False),
        sa.Column("minimum_margin", sa.Numeric(4, 2), nullable=False),
        sa.Column("target_margin", sa.Numeric(4, 2), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamps(),
    )
    op.create_table(
        "price_positions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "price_list_id",
            sa.Integer(),
            sa.ForeignKey("price_lists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("la", sa.String(50), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey("roles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("sales_price", sa.Numeric(12, 2), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "ix_price_positions_price_list_id", "price_positions", ["price_list_id"]
    )
    connection = op.get_bind()
    settings = connection.execute(
        sa.text(
            "SELECT min_contribution_margin_percent, contribution_margin_percent "
            "FROM daily_rate_settings ORDER BY id LIMIT 1"
        )
    ).first()
    lists = sa.table(
        "price_lists",
        sa.column("id", sa.Integer),
        sa.column("name"),
        sa.column("cost_basis"),
        sa.column("hours_per_day"),
        sa.column("minimum_margin"),
        sa.column("target_margin"),
        sa.column("archived", sa.Boolean),
        sa.column("version"),
    )
    sheet_id = connection.execute(
        lists.insert()
        .values(
            name="Bestand",
            cost_basis="day",
            hours_per_day=8,
            minimum_margin=settings[0] if settings else 30,
            target_margin=settings[1] if settings else 35,
            archived=False,
            version=1,
        )
        .returning(lists.c.id)
    ).scalar_one()
    rates = connection.execute(
        sa.text(
            "SELECT d.role_id, r.name, d.production_cost, d.list_price "
            "FROM daily_rates d JOIN roles r ON r.id = d.role_id ORDER BY r.name, d.id"
        )
    ).all()
    positions = sa.table(
        "price_positions",
        *[
            sa.column(name)
            for name in (
                "price_list_id",
                "sort_order",
                "la",
                "label",
                "role_id",
                "cost",
                "sales_price",
            )
        ],
    )
    for index, rate in enumerate(rates):
        connection.execute(
            positions.insert().values(
                price_list_id=sheet_id,
                sort_order=index,
                la="",
                label=rate[1],
                role_id=rate[0],
                cost=rate[2],
                sales_price=rate[3],
            )
        )


def downgrade() -> None:
    # Legacy tables remain intact, so rollback restores the original inputs.
    op.drop_index("ix_price_positions_price_list_id", table_name="price_positions")
    op.drop_table("price_positions")
    op.drop_table("price_lists")
