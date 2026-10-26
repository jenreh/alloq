"""Replace the seeded Word layout of quo_v1 with the cleaned file.

The first seed stored the layout with reviewer comments, people and author
names. Template versions and drafts that still point at such a blob get the
cleaned file from ``alembic/seed``; the old blob is deleted when nothing else
uses it. The cleaning cannot be undone, so the downgrade keeps the clean file.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-11-01 10:00:00.000000
"""

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LAYOUT_PATH = Path(__file__).resolve().parent.parent / "seed" / "quo_v1_layout.docx"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
# SHA-256 of the layout files earlier seeds stored.
OLD_LAYOUTS = (
    "a361686391fba5c391dd3deaffb06622a7cc25ad5abb7caa8264e11c3fd325cd",
    "7396ab4094b362f373496d5af2496afd7c8666299be30d1083e58914d3b9f4ff",
)

_blobs = sa.table(
    "offer_blobs",
    sa.column("id", sa.Integer),
    sa.column("sha256", sa.String),
    sa.column("size", sa.Integer),
    sa.column("mime", sa.String),
    sa.column("data", sa.LargeBinary),
    sa.column("created", sa.DateTime),
    sa.column("updated", sa.DateTime),
)
_versions = sa.table("offer_template_versions", sa.column("layout_blob_id", sa.Integer))
_templates = sa.table("offer_templates", sa.column("draft_layout_blob_id", sa.Integer))
_IN_USE = sa.text(
    "SELECT 1 FROM offer_sources WHERE blob_id = :id "
    "UNION ALL SELECT 1 FROM offer_exports WHERE blob_id = :id "
    "UNION ALL SELECT 1 FROM offer_template_versions WHERE layout_blob_id = :id "
    "UNION ALL SELECT 1 FROM offer_templates WHERE draft_layout_blob_id = :id"
)


def _clean_blob(bind: Connection, layout: bytes) -> int:
    digest = hashlib.sha256(layout).hexdigest()
    found = bind.scalar(sa.select(_blobs.c.id).where(_blobs.c.sha256 == digest))
    if found is not None:
        return found
    now = datetime.now(UTC)
    return bind.execute(
        _blobs.insert()
        .values(
            sha256=digest,
            size=len(layout),
            mime=DOCX_MIME,
            data=layout,
            created=now,
            updated=now,
        )
        .returning(_blobs.c.id)
    ).scalar_one()


def replace_layouts(bind: Connection, layout: bytes) -> int:
    """Point every use of an old layout at ``layout``; returns the number replaced."""
    old_ids = list(
        bind.scalars(sa.select(_blobs.c.id).where(_blobs.c.sha256.in_(OLD_LAYOUTS)))
    )
    if not old_ids:
        return 0
    clean_id = _clean_blob(bind, layout)
    replaced = bind.execute(
        _versions.update()
        .where(_versions.c.layout_blob_id.in_(old_ids))
        .values(layout_blob_id=clean_id)
    ).rowcount
    replaced += bind.execute(
        _templates.update()
        .where(_templates.c.draft_layout_blob_id.in_(old_ids))
        .values(draft_layout_blob_id=clean_id)
    ).rowcount
    for blob_id in old_ids:
        if bind.execute(_IN_USE, {"id": blob_id}).first() is None:
            bind.execute(_blobs.delete().where(_blobs.c.id == blob_id))
    return replaced


def upgrade() -> None:
    replace_layouts(op.get_bind(), LAYOUT_PATH.read_bytes())


def downgrade() -> None:
    # The removed comments and names are not brought back; the clean layout
    # works with the previous revision as well.
    pass
