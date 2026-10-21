# Refined prompt: "Angebote" page as new package `alloq-offer`

> Load `alloq-implementation` first, then `appkit-mantine-reference` before using any `mn.*` component you have not used in this task. Follow the test-first workflow and definition of done from that skill.

## Task

Add a new page **Angebote** (`/offers`) that lists offers calculated for customer projects. It looks and behaves like the Projekte list view: a macOS-style table with status groups, a toolbar with search, filter segments and a "Angebot anlegen" button, and an inspector on the right that shows the clicked offer. Offers can be created and edited, but never deleted; they can be archived and restored.

The feature lives in a **new, independent uv workspace package `components/alloq-offer`** (import name `alloq_offer`). Entity, model, repository, services, states, components and the page factory all live in this package. It depends only on `alloq-commons` and appkit, never on `alloq-project`, `alloq-team`, `alloq-dashboard` or `app`.

Access is controlled by a **new permission role `offer_editor`** (label "Angebote"). Admins, project managers and users with `offer_editor` may see and edit offers. Nobody else sees the page or its sidebar entry.

## Context (found in the repo)

- Reference slice to copy the shape from: the Projekte list view.
  - Page factory: `components/alloq-project/src/alloq_project/pages.py` → `create_projects_overview_page` (uses `app_page`, `window_toolbar`, `viewer_only(..., fallback=no_access())`).
  - Table: `alloq_project/components/project_table.py` (`TEMPLATE`, `COLUMNS`, `_row`, `_group`, `split_view`, `list_header`, `list_row`, `cell_main`, `badge`, `number`, `empty_list`).
  - Inspector: `alloq_project/components/project_inspector.py` (`inspector`, `inspector_section`, `key_values`, `plain_button`, inline `mn.select` for status, inline `mn.date_input` with "Heute" action icon, copy-to-clipboard action icon in `_booking_number`).
  - Toolbar: `alloq_project/components/project_toolbar.py` (`segmented`, `toolbar_search`, `icon_button("panel-right", ...)`, `primary_button`).
  - List state mixin: `alloq_project/states/project_list_state.py` (`FILTERS`, `STATUS_TONES`, `inspected_id`, `inspector_open` as `rx.LocalStorage`, `show_inspector`, grouped row computed vars).
  - Create modal: `add_project_modal` in `alloq_project/components/project_overview.py`; shared parts `modal_form_layout`, `modal_footer` in `alloq_commons/components/modal_layout.py`.
- Shared UI parts: `alloq_commons/components/list_view.py`, `toolbar.py`, `formatters.py` (`de_number`), `shell.py` (`app_page`). Colors only from `alloq_commons.theme`.
- Entity/repo pattern: `alloq_commons/entities/department.py`, `alloq_commons/repositories/department_repository.py` (`BaseRepository[XEntity, AsyncSession]`, module singleton). Money columns use `Numeric` + `Decimal` like `alloq_commons/entities/price_list.py`. Enum-as-German-label pattern: `ProjectStateEnum(enum.StrEnum)` in `alloq_commons/entities/project.py`.
- Package template: `components/alloq-team/pyproject.toml` and its `src/alloq_team/{components,services,states,pages.py}` + `tests/` layout.
- Roles and access: `alloq_commons/roles.py` (`PROJECT_MANAGER_ROLE` id 1, `EMPLOYEE_ROLE` id 2, `ALL_ROLES`), `alloq_commons/access.py` (`CAN_EDIT`, `editor_only`, `_guard`, `requires_editor`, `ACCESS_LEVEL_ATTR`). The word "editor" is already used there for admin + project manager, so the new role is named `offer_editor`.
- Sidebar: `app/components/sidebar.py` (`PLANNING_ITEMS`, `VIEWER_ROUTES`, `_guarded_nav_item`). Registration: `app/app.py`.
- Guards: `tests/test_handler_authorization.py` (`PACKAGES`, `EDITOR_PACKAGES`, `UI_ONLY_HANDLERS`, access-level checks), `tests/test_component_boundaries.py`.
- Migrations: current head is `bd91ef12ac34` (`alembic/versions/2026_10_19_department_highlight.py`); `alembic/env.py` imports `alloq_commons.entities` to register tables; new revisions go first in `KNOWN_REVISIONS` in `app/desktop/schema.py`.
- Root `pyproject.toml` lists every package in `dependencies`, `[tool.uv.sources]`, `[[tool.bumpversion.files]]`, pytest `testpaths` and coverage `source`.

## Requirements

### 1. Package scaffold
1. Create `components/alloq-offer/pyproject.toml` (copy `alloq-team`, name `alloq-offer`, same version, dependency `alloq-commons`, wheel package `src/alloq_offer`).
2. Layout: `src/alloq_offer/{__init__.py, entities.py, models.py, repository.py, services/, states/, components/, pages.py}` and `tests/`. Split into sub-modules only if a file grows large.
3. Register in root `pyproject.toml`: `dependencies`, `[tool.uv.sources]`, a `[[tool.bumpversion.files]]` block, `testpaths`, coverage `source`. Run `uv sync` (via `task sync`).

### 2. Data layer (in `alloq_offer`)
4. Enums (`enum.StrEnum`, values are the German labels shown in the UI):
   - `OfferStateEnum`: `NEW = "Neu"`, `IN_PROGRESS = "In Bearbeitung"`, `SENT = "Versendet"`.
   - `CustomerIndustryUnit`: values are the codes `CP, FS, U, P, H, IMC`, plus a module constant `CIU_LABELS` mapping code → label: "Consumer Services - CP", "Financial Services - FS", "Utilities - U", "Public - P", "Health - H", "Industrial Midcaps - IMC".
5. `OfferEntity(Entity, Base)`, table `offers`:
   | Column | Type | Rule |
   | --- | --- | --- |
   | `title` | String(255) | required |
   | `customer` | String(255) | required |
   | `person_days` | Numeric(8,2) | required, ≥ 0 ("PT") |
   | `risk_buffer_days` | Numeric(8,2) | required, ≥ 0, default 0 ("Risikopuffer (PT)") |
   | `production_cost` | Numeric(12,2) | required, ≥ 0 ("Herstellkosten (HK)", €) |
   | `recommended_price` | Numeric(12,2) | required, ≥ 0 ("Empfohlener VK", €) |
   | `key_accounter` | String(255) | required, free text |
   | `ciu` | String(10) | required, one of the CIU codes |
   | `sharepoint_url` | String(2048) | optional |
   | `sent_date` | Date | optional |
   | `state` | String(20) | required, default `Neu` |
   | `archived` | Boolean | not null, default false, `server_default=false()` |
   `to_dict()` returns every field plus `id`, `created`, `updated`.
6. Pydantic `Offer` read model and `OfferCreate` write model with `Field` limits matching the columns; `sharepoint_url` must be empty or start with `http://` or `https://`; `ciu` and `state` validated against the enums; strings stripped and non-empty where required.
7. `OfferRepository(BaseRepository[OfferEntity, AsyncSession])` with `find_all_ordered()` (newest `updated` first) and module singleton `offer_repo`. No delete method is used anywhere.
8. Make the table known to Alembic: `alloq_offer` must register `OfferEntity` on `Base.metadata`, and `alembic/env.py` imports `alloq_offer.entities` next to `alloq_commons.entities`. Make sure the SQLite test setup also sees the table.
9. Hand-written migration `alembic/versions/2026_10_21_offers.py`: new revision id, `down_revision = "bd91ef12ac34"`, `op.create_table("offers", ...)` with all columns and an index on `state`; real `downgrade()` dropping the table. Add the revision as first entry of `KNOWN_REVISIONS` in `app/desktop/schema.py`.

### 3. Pure services (`alloq_offer/services/`)
10. `apply_state_change(state: str, sent_date: date | None, new_state: str, today: date) -> date | None`: when `new_state` is `Versendet` and `sent_date` is empty, return `today`; otherwise return `sent_date` unchanged (moving back to Neu/In Bearbeitung keeps the date). Used by create, edit and the inline status select.
11. Derived values for the inspector: `total_days = person_days + risk_buffer_days`, `margin_pct = (recommended_price - production_cost) / recommended_price * 100` (None when VK is 0). Plain functions, unit-tested.
12. Filtering/grouping helpers: search over title, customer and key accounter (case-insensitive); filter segments; sort by column.

### 4. Roles and access (small, shared touchpoints in `alloq_commons`)
13. `alloq_commons/roles.py`: add `OFFER_EDITOR_ROLE = Role(id=3, name="offer_editor", label="Angebote", description="Lesen und Bearbeiten der Angebote")` and append it to `ALL_ROLES` so it appears in user management.
14. `alloq_commons/access.py`: add `CAN_EDIT_OFFERS` (frontend Var: `CAN_EDIT | roles.contains("offer_editor")`), `can_edit_offers(user)`, `offers_only(*children, fallback=None)` and `requires_offer_editor` built on the existing `_guard` with access level `"offer_editor"`. Do not change the meaning of the existing levels: an `offer_editor`-only user gets no planning, projects or team access.
15. Every data handler in `alloq_offer` states uses `@rx.event` + `@requires_offer_editor`; UI-only handlers (open/close modal, set filter, search, inspect, toggle inspector) have no decorator and are listed in `UI_ONLY_HANDLERS["OfferState"]`.
16. `tests/test_handler_authorization.py`: add `"alloq_offer"` to `PACKAGES`; add an `OFFER_PACKAGES = {"alloq_offer"}` rule so handlers there must carry the `offer_editor` level (and treat that level as guarded); add a test that offer handlers are not `requires_admin`/`requires_editor`. Keep all existing tests green.

### 5. State (`alloq_offer/states/offer_state.py`)
17. `OfferState(rx.State)` with `offers`, `is_loading`, `search_filter`, `list_filter`, `sort_column`, `sort_desc`, `inspected_id`, `inspector_open` (`rx.LocalStorage("1", name="alloq_offers_inspector")`), `form_open`, `editing_id` (0 = create), and form draft fields. If the file nears ~400 lines, move list logic into a mixin (`rx.State, mixin=True`), never a substate.
18. Handlers: `load_offers`, `create_offer(form_data)`, `update_offer(form_data)`, `update_inspected_state(offer_id, state)` (applies requirement 10 and saves), `set_inspected_sent_date(offer_id, value)` + save on blur, `set_sent_date_today(offer_id)`, `archive_offer(offer_id)`, `restore_offer(offer_id)`. Error shape per skill: `ValidationError` → German hint toast, `Exception` → `logger.exception` + generic German error toast. Success toasts in German.
19. Computed vars: grouped rows `new_rows`, `in_progress_rows`, `sent_rows`, `archived_rows`; `inspected` offer; `row_count`; totals for the footer.

### 6. UI (`alloq_offer/components/`)
20. **Toolbar** (`window_toolbar("Angebote", subtitle, center=filter, actions=...)`): filter segments `Alle`, `Neu`, `In Bearbeitung`, `Versendet`, `Archiviert`; `toolbar_search` placeholder "Angebot, Kunde oder Key Accounter"; inspector toggle `icon_button("panel-right", ...)`; `offers_only(primary_button("Angebot anlegen", "plus", ...))`. No grid/card view toggle (list only).
21. **Table** (`split_view` with inspector): columns `Angebot` (title + customer via `cell_main`), `CIU` (badge with code), `Status` (badge, tones: Neu → info, In Bearbeitung → warning/accent, Versendet → positive), `PT` (person days + buffer, `de_number`), `HK` (€), `VK` (€), `Versendet am` (DD.MM.YYYY or "–"). Groups: Neu, In Bearbeitung, Versendet; archived offers are hidden except under the `Archiviert` filter, where they form one group. Footer row with sums of PT, HK and VK. Sortable headers. Click selects into the inspector; double click opens the edit modal. Empty state "Keine Angebote mit diesem Filter." / "Noch keine Angebote vorhanden."
22. **Create/edit modal** (`mn.modal` + `modal_form_layout`/`modal_footer`), title "Neues Angebot" / "Angebot bearbeiten". Fields, German labels:
    - Angebotstitel (text, required)
    - Kunde (text, required)
    - Kalkulierte Personentage (PT) (number, ≥ 0, 2 decimals)
    - Risikopuffer (PT) (number, ≥ 0, default 0)
    - Herstellkosten (HK) (number, €, ≥ 0)
    - Empfohlener VK (number, €, ≥ 0)
    - Key Accounter (text, required)
    - CIU (`mn.select` with the six labels, required)
    - SharePoint-Link (URL text input, optional)
    - Versendet am (`mn.date_input`, `locale="de"`, `value_format="DD.MM.YYYY"`, clearable)
    - Status (`mn.select`: Neu, In Bearbeitung, Versendet; default Neu)
    Use `custom_attrs={"maxLength": N}` for text limits (not `max_length`). Save button disabled while required fields are empty. Key the uncontrolled inputs by a form version so reopening resets them.
23. **Inspector** (`inspector(..., label="Angebotsdetails")`), shown for the selected row, "Kein Angebot ausgewählt." otherwise:
    - Heading: title, customer, status badge; "Archiviert" tag when archived.
    - Actions (inside `offers_only`): "Bearbeiten" (opens edit modal), "Archivieren" / "Wiederherstellen".
    - Section "Eckdaten" (`key_values`): Status as inline `mn.select` (applies requirement 10), Versendet am as inline `mn.date_input` with a "Heute" action icon, saved on blur (copy `_date_input` from the project inspector), CIU label, Key Accounter, SharePoint link as an anchor opening in a new tab plus a copy action icon ("–" when empty).
    - Section "Kalkulation": PT, Risikopuffer, Gesamt-PT, HK, Empfohlener VK, Marge in % (from requirement 11).
    - Controls disabled via `disabled=~CAN_EDIT_OFFERS`.

### 7. Page, sidebar, registration
24. `alloq_offer/pages.py`: `create_offers_page(sidebar, route="/offers", title="Angebote")` using `app_page(..., padded=False, on_load=[OfferState.load_offers])`; body wrapped in `offers_only(..., fallback=no_access())`.
25. `app/app.py`: `create_offers_page(sidebar())`.
26. `app/components/sidebar.py`: add `("/offers", "Angebote", "file-text")` to `PLANNING_ITEMS` after Projekte; `_guarded_nav_item` uses `offers_only` for that route (e.g. a small route → guard mapping instead of the `VIEWER_ROUTES` if/else).

## Deliverables

- `components/alloq-offer/` package with `pyproject.toml`, source modules above, `tests/`.
- Edits: root `pyproject.toml`, `alembic/env.py`, `alembic/versions/2026_10_21_offers.py`, `app/desktop/schema.py`, `alloq_commons/roles.py`, `alloq_commons/access.py`, `app/app.py`, `app/components/sidebar.py`, `tests/test_handler_authorization.py`.
- Tests in `components/alloq-offer/tests/`:
  - `test_offer_model.py`: `to_dict()` keys; `OfferCreate` rejects empty title/customer, negative numbers, unknown CIU/state, non-http SharePoint URL.
  - `test_offer_services.py`: `apply_state_change` (empty date set on Versendet, existing date kept, date kept when moving back), totals, margin incl. VK = 0, search/filter/grouping/sorting.
  - `test_offer_state.py`: create, update, inline state change sets date, sent-date edit, archive/restore, filter `Archiviert`, error toasts; patch `MODULE.offer_repo` and `MODULE.get_asyncdb_session`, helpers copied from `components/alloq-commons/tests/test_departments.py`.
  - `test_offer_components.py`: render table, inspector, modal with `str(...)`; assert on module constants (umlauts are escaped).
  - Access tests in `alloq-commons` tests: `can_edit_offers` true for admin, project manager, offer_editor; false for employee and a user without roles; `can_edit` / `can_view` unchanged for an offer_editor-only user.

## Success criteria

- `task format && task lint && task typecheck && task test` all green, coverage ≥ 80 %.
- `tests/test_handler_authorization.py` and `tests/test_component_boundaries.py` green; `alloq_offer` imports nothing from `app` or other feature packages.
- `uv run alembic upgrade head` then `downgrade -1` works on a fresh SQLite DB.
- `python .claude/skills/alloq-implementation/scripts/check_file_sizes.py` passes.
- Manual check on localhost: as admin, open `/offers`, create an offer, select it, change status to Versendet in the inspector and see today's date appear, change the date by hand, archive and find it under `Archiviert`, restore it. A user with only `offer_editor` sees only Angebote in the Planung section; an employee does not see Angebote.
- Memory updated with new decisions (independent package, `offer_editor` role and access level).

## Out of scope

- Deleting offers (archive only).
- Converting an offer into a project or linking offers to projects.
- Calculating PT, HK or VK from price lists or daily rates; all values are entered by hand.
- Card/grid view, export, attachments or SharePoint integration beyond storing the link.
- Sidebar badge counts for offers.
- Changing access for existing pages or roles.
