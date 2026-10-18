# Database schema

[schema.html](schema.html) is an interactive entity-relationship diagram of every
table on `Base.metadata`: the alloq tables from `alloq_commons.entities` and the
login tables from `appkit_user`. Open it in a browser. It shows every column with
its PostgreSQL type, the keys, and one line per foreign key labelled with its
`ON DELETE` action.

| File | Purpose |
| --- | --- |
| `schema.erd.json` | Source of the diagram. Edit this file. |
| `schema.html` | Rendered diagram. Never edit by hand. |
| `schema.delivery.json` | Render receipt. It records the hashes of the JSON and the HTML. |

## Keeping it in sync

`tests/test_schema_doc.py` fails when the JSON and the SQLAlchemy models differ
(tables, columns, types, keys, foreign keys) or when the HTML was not rendered
from the current JSON. After a change to an entity or a migration:

1. Run `uv run pytest tests/test_schema_doc.py -q`. A failing column test prints
   the expected attributes of the table.
2. Update `schema.erd.json`. Place a new table in the grid (`row`, `col`) next to
   the tables of its domain (`tag`) and add a relationship for each new foreign
   key. Self-references cannot be drawn; mention them in the Conventions card.
3. Re-render with the archify skill (`/archify`), or run from the repo root:

   ```bash
   node ~/.claude/skills/archify/bin/archify.mjs finalize erd doc/database/schema.erd.json doc/database/schema.html --quality standard --out-dir /tmp/archify-schema --json
   ```

4. Run the test again and commit all three files.

Conventions in the JSON: types are PostgreSQL types, a trailing `null` marks a
nullable column, and the relationship `label` is the lowercase `ON DELETE` action.
