"""Move the offer CIU codes into an editable industries (Branchen) table.

Seeds one industry per former CIU code, links every offer through
``industry_id`` and drops the ``ciu`` column. Codes outside the known six
become an industry named after the code, so no offer loses its value.

Revision ID: f1a2b3c4d5e6
Revises: e023b4c5d6f7
Create Date: 2026-10-21 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e023b4c5d6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDUSTRIES: dict[str, str] = {
    "CP": "Verbraucherdienstleistungen",
    "FS": "Finanzdienstleistungen",
    "U": "Energie und Versorgung",
    "P": "Öffentlicher Sektor",
    "H": "Gesundheitswesen",
    "IMC": "Industrie und Mittelstand",
}
"""Former CIU code -> industry name."""

FK_NAME = "fk_offers_industry_id_industries"
INDEX_NAME = "ix_offers_industry_id"


def upgrade() -> None:
    industries = op.create_table(
        "industries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
    )
    conn = op.get_bind()
    unknown = [
        code
        for (code,) in conn.execute(sa.text("SELECT DISTINCT ciu FROM offers"))
        if code not in INDUSTRIES
    ]
    names = {**INDUSTRIES, **{code: code for code in unknown}}
    op.bulk_insert(industries, [{"name": name} for name in names.values()])

    with op.batch_alter_table("offers") as batch:
        batch.add_column(sa.Column("industry_id", sa.Integer(), nullable=True))
    for code, name in names.items():
        conn.execute(
            sa.text(
                "UPDATE offers SET industry_id = "
                "(SELECT id FROM industries WHERE name = :name) WHERE ciu = :code"
            ),
            {"name": name, "code": code},
        )
    with op.batch_alter_table("offers") as batch:
        batch.alter_column("industry_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            FK_NAME, "industries", ["industry_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_index(INDEX_NAME, ["industry_id"])
        batch.drop_column("ciu")


def downgrade() -> None:
    """Restore the codes; industries added later keep their first 10 chars."""
    conn = op.get_bind()
    with op.batch_alter_table("offers") as batch:
        batch.add_column(sa.Column("ciu", sa.String(10), nullable=True))
    codes = {name: code for code, name in INDUSTRIES.items()}
    rows = conn.execute(sa.text("SELECT id, name FROM industries")).all()
    for industry_id, name in rows:
        conn.execute(
            sa.text("UPDATE offers SET ciu = :code WHERE industry_id = :id"),
            {"code": codes.get(name, name[:10]), "id": industry_id},
        )
    with op.batch_alter_table("offers") as batch:
        batch.alter_column("ciu", existing_type=sa.String(10), nullable=False)
        batch.drop_index(INDEX_NAME)
        batch.drop_constraint(FK_NAME, type_="foreignkey")
        batch.drop_column("industry_id")
    op.drop_table("industries")
