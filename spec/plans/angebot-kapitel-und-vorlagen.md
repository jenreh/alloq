# Refined prompt: Offer chapters as a document editor, templates and prompts in one "Angebote" admin menu — multiphase plan

> Load `alloq-implementation` first in **every** phase, then the skills listed under "Load first". Follow the test-first workflow and the definition of done of `alloq-implementation`. One phase = one reviewable commit. Do not start a phase before the previous one is green. Builds on `spec/plans/ki-angebotswerkstatt.md` (the workshop as it exists today).

### UI design (binding)

The Kapitel tab follows the board **"A + C · 2 Kapitel im Dokument: Kapiteltypen"** (`project/Kapitel.dc.html`) on the prototype canvas <https://claude.ai/artifact/SqvwnLbKttsfEL7XwnTcYX>. Read it before Phase 4 (Artifact tool, action `read`, `path` = `project/Kapitel.dc.html`) and match its layout, texts and states. Build with `mn.*`, Alloq shell parts and `alloq_commons/theme.py` tokens. Where this plan and the board differ, this plan wins (floating module toolbar, drag and drop, no story scope). Note every other deviation in the commit message.

## Context
The "Kapitel" tab of the offer workshop is a three-column list/editor/inspector today. Each
chapter is edited on its own, the outline is fixed by `templates/quo_v1/chapters.yaml`, and
chapter prompts are hard-wired. The prototype (screenshot "KI-gestützte Bearbeitung von
Kundenanfragen") shows the target: one continuous document that feels like a word processor,
an outline that the team can extend and reorder, and a context panel per chapter type.
Admins must be able to build templates from reusable chapter blocks and maintain the AI
prompts without a code change.

The work is large. Implement it in the phases below, one phase per commit, each phase green
on `task lint`, `task typecheck` and `task test` before the next starts.

---

## Task
1. Rebuild the Kapitel tab as a document view like the prototype: outline left, all
   chapters as stacked blocks in the middle, a chapter panel right. Only the selected
   chapter is editable and shows its own toolbar.
2. Let users add chapters (from the library or blank), remove optional ones, and reorder
   them by drag and drop. Required chapters cannot be removed. The fixed legal frame of the
   Word layout stays pinned at start and end.
3. Move templates, reusable chapter blocks, rule checks, the Word layout and all AI prompts
   from code files into the database, edited in one new admin menu "Angebote".

## Load first
`alloq-implementation` (mandatory), then `reflex-state-and-architecture`,
`appkit-mantine-reference`, `appkit-commons`, `reflex-testing-state`, `german-ui-copy`.

## Existing code to build on (all under `components/alloq-offer/src/alloq_offer/workshop/`)
| Area | Files | Notes |
| --- | --- | --- |
| Template loader | `export/template_package.py` | `load_template(key)` (cached) builds `TemplatePackage` from YAML + `layout.docx`; `ChapterDef`, `CHAPTER_ANCHOR`, `check_layout()` |
| Template call sites | `services/chapters.py`, `services/findings.py`, `services/workspace.py`, `services/export_snapshot.py`, `jobs/draft_chapters.py`, `jobs/export_docx.py` | All call `load_template(workspace.template_key)` |
| Template data | `templates/quo_v1/chapters.yaml`, `rules.yaml`, `layout.docx` | Layout holds the legal frame (Rechtlicher Hinweis, Inhaltsverzeichnis before `[[KAPITEL]]`; Rechtliche Bestimmungen, Bindefrist, Sonstiges, Anlagen, Unterschriften after) |
| Content model | `content/schema.py`, `content/editor_io.py`, `content/text.py` | Types `prose`, `table`, `stories`, `calc`; HTML ⇄ block tree |
| Chapters service | `services/chapters.py` | Revisions, conflict check (A08), proposals, protection, `default_content()`, `mark_dependent_review()` |
| Chapter state / UI | `states/chapter_state.py`, `components/chapters_tab.py`, `components/review_panel.py` | Autosave with debounce, AI help, history, findings |
| Entities | `entities.py` | `WorkspaceEntity.template_key/template_version`, `ChapterEntity` (unique `offer_id, chapter_key`), `ChapterRevisionEntity`, `ProposalEntity`, `FindingEntity`, `SnapshotEntity`, `BlobEntity` |
| Blob storage | `storage.py`, `BlobEntity` | Reuse for uploaded layout files |
| Prompts | `ai/agents.py` (`load_prompt`, `*_PROMPT` names, `*_prompt_version` attrs), `ai/prompts/*.md`, `ai/render.py`, `ai/port.py`, `ai/demo.py` | `GenerationRunEntity` records the prompt version |
| Export | `export/docx_renderer.py`, `export/chapter_renderers.py` | Uses `chapter.title/level` from the snapshot |
| Admin pages | `app/pages/industries.py` (pattern: `app_page(..., admin_only=True)`, `window_toolbar`, `requires_admin`), `app/components/sidebar.py` (`ADMIN` nav list) | |
| Editor | `mn.rich_text_editor` (`appkit_mantine/tiptap.py`) has `show_toolbar`, `sticky`, `sticky_offset`, `editable`, `control_groups` | |
| Theme/CSS | `alloq_commons/theme.py`, `assets/css/aq-workshop.css` | |

Repo rules that apply (from memory and CLAUDE.md):
- Offers are edited by `offer_editor` only (`requires_offer_editor`), admins do not edit offers.
  The admin menu needs the admin switch (`requires_admin` on the page and on every handler).
- Big state logic goes into mixins, not substates. Keep DB handlers in the module tests patch.
- Static layout CSS goes in `assets/css/aq-*.css`. Page popovers use `theme.PAGE_POPOVER_Z_INDEX`.
- Hand-written Alembic revisions in `alembic/versions/` (date-prefixed names). Never run
  `alembic upgrade`; hand the command to the user. Run the `migration-reviewer` agent.
- Sort German names in Python, not in SQL. Files ≤ 1000 lines. No f-strings in logger calls.
- German UI text, Sie-form, as in the existing tab.

---

## Decisions (agreed with the user)
- **Frame:** the legal blocks from the Word layout stay pinned at start and end and cannot
  be moved or removed. Required content chapters can be moved but not removed. Optional and
  added chapters can be moved and removed.
- **"+ Kapitel"** offers library blocks (with default content, rules and prompt) and a blank
  chapter of a chosen type (Text, Tabelle, User Stories, Werte).
- **Prompts:** global system prompts (chapter, map, map additions, briefing, review) are
  editable and versioned in admin. Each library block adds its own instructions on top
  (Leitfrage, Regeln, extra prompt text).
- **Admin scope now:** templates, chapter blocks, prompts, Word layout upload, rule checks.
  Branchen stays on its own page.
- **Template changes never alter existing offers** (spec 6.1). A template is edited as a
  draft and published as an immutable version. A workspace binds `template_key` +
  `template_version`. On creation the offer copies the outline and chapter settings into its
  own chapters.

---

## Phase 1: Data model and migration
New entities in a new module `workshop/template_entities.py` (keeps `entities.py` under the
line limit):
- `ChapterBlockEntity` (`offer_chapter_blocks`): `key` (unique slug), `title`,
  `chapter_type`, `level` (1 or 2), `default_content` (JSON, validated by `parse_content`),
  `guiding_question`, `content_rules` (JSON list), `prompt_text`, `required_info` (JSON list),
  `checks` (JSON list, values limited to the check names known in `services/checks.py`),
  `active`.
- `OfferTemplateEntity` (`offer_templates`): `key` (unique), `name`, `description`, `active`,
  `draft_layout_blob_id`, `frame_before` / `frame_after` (JSON lists of headings).
- `OfferTemplateChapterEntity` (`offer_template_chapters`): `template_id`, `block_id`,
  `position`, `required`, optional `title` and `level` overrides. Draft outline only.
- `OfferTemplateVersionEntity` (`offer_template_versions`): `template_id`, `number`,
  `payload` (JSON: full outline with resolved block settings, frame lists), `layout_blob_id`,
  `published_by`, `created`. Immutable.
- `PromptEntity` (`offer_prompts`): `name` (chapter, map, map_additions, briefing, review),
  `version` (int), `text`, `active`, `author`. Unique (`name`, `version`); one active per name.

Changes to `ChapterEntity`: add `position`, `title`, `chapter_type`, `level`, `required`,
`block_key` (nullable, origin library block), `settings` (JSON snapshot: guiding question,
rules, prompt text, required_info, checks), `removed_at` (soft delete, so revisions, findings
and restore keep working). New chapters added in an offer get key `custom_<8 hex>`.

Migration (one hand-written revision):
1. Create the tables above.
2. Add the new `offer_chapters` columns (nullable first).
3. Seed: one `ChapterBlockEntity` per entry of `quo_v1/chapters.yaml` (rules from
   `rules.yaml`), template `quo_v1` with its draft outline and published version `1`
   (`payload` from the YAML, layout bytes stored as a blob, `frame_before`/`frame_after`
   read from the layout headings), and the five prompts from `ai/prompts/*.md` as version 1.
   Version string mapping: existing workspaces keep `template_version = "quo_v1.0"`; map
   that to version 1.
4. Backfill existing `offer_chapters` rows: `position`, `title`, `chapter_type`, `level`,
   `required`, `block_key`, `settings` from the seeded quo_v1 payload. Then set NOT NULL.
Seed data lives in the migration as literals (no import of app code). After the migration,
delete `templates/quo_v1/*.yaml` and `ai/prompts/*.md`. Keep `layout.docx` only as a test
fixture under `tests/fixtures/` if tests need it.

## Phase 2: DB-backed template and prompt access
- Replace `load_template` with a `TemplateService` (`services/templates.py`) that loads a
  published `OfferTemplateVersionEntity` by (`key`, `version`) into the existing
  `TemplatePackage` shape. `layout_bytes` comes from the blob instead of a file path. Keep a
  small in-process cache keyed by (`key`, `version`); versions are immutable so no
  invalidation is needed.
- Per-offer code must use the offer's own chapters, not the template: `mark_dependent_review`,
  `services/findings.py` (rules per chapter now come from `ChapterEntity.settings`),
  `jobs/draft_chapters.py` (guiding question, rules and prompt text from `settings`),
  `services/export_snapshot.py` (order by `position`, skip `removed_at`, title/level from the
  chapter). Only `services/workspace.py` (new offer) and `jobs/export_docx.py` (layout and
  frame) still need the template version.
- `services/workspace.py`: on open, pick the latest published version of the default (or
  chosen) template and copy its outline into `offer_chapters` with `default_content` as
  revision 1.
- `ai/agents.py`: `load_prompt(name)` reads the active `PromptEntity`; the agent's
  `*_prompt_version` attributes become `"<name>@<version>"` so `GenerationRunEntity` keeps
  recording which prompt text ran. The chapter request (`ai/port.py`, `ai/render.py`) gets the
  chapter's `prompt_text` as an extra tagged section after Leitfrage and Regeln. `ai/demo.py`
  keeps working without DB prompts.

## Phase 3: Outline operations in the chapters service
Add to `services/chapters.py` (or a new `services/outline.py` if the file would pass 1000
lines; keep the DB calls where tests patch them):
- `add_chapter(offer_id, after_key, block_key | chapter_type, title)`: inserts at the given
  position, revision 1 from block default content or the empty default of the type.
- `remove_chapter(offer_id, key)`: refuses required chapters ("Pflichtkapitel können nicht
  entfernt werden."), sets `removed_at`. A removed chapter can be restored from a small
  "Entfernte Kapitel" list.
- `move_chapter(offer_id, key, new_index)`: renumbers positions in one transaction; the frame
  is not part of the list, so it can never be moved.
- `rename_chapter(offer_id, key, title)` and `set_level(offer_id, key, level)`.
- Numbering (1, 2, 2.1, …) is computed from `position` and `level` in one pure function and
  used by the UI and the export.
All handlers: `requires_offer_editor`, blocked while the chapter is protected or the offer is
archived, same conflict rules as content saves.

## Phase 4: Document view (Kapitel tab)
Rewrite `components/chapters_tab.py` into small modules under `components/chapters/`
(`outline.py`, `document.py`, `blocks/prose.py`, `blocks/table.py`, `blocks/stories.py`,
`blocks/calc.py`, `panel.py`) and split `states/chapter_state.py` into the existing state
plus mixins (`OutlineMixin`, `ChapterPanelMixin`).
- **Layout** like the screenshot: outline column (about 280px, sticky), document column
  (white page card, max width about 900px, centered, page-like padding), panel column (about
  360px, sticky, existing `inspector`). CSS in `assets/css/aq-workshop.css`.
- **Outline:** header "Gliederung" with "+ Kapitel" link button. Frame entries from the
  template in muted grey, not draggable. Chapters with number, title and a type badge
  (Text, Stories, Tabelle, Werte); selected row highlighted with `theme.ACCENT_SOFT`. Status
  badges (Blocker, Befunde, Bitte prüfen, Vorschlag, Geschützt) as small dots or badges.
  Drag handle (grip icon) on hover for movable chapters. Click scrolls the document to the
  chapter and selects it.
- **Drag and drop:** wrap `@hello-pangea/dnd` (the library Mantine's docs use for sortable
  lists) as a small Reflex component in `alloq_commons/components/sortable.py` with an
  `on_reorder(key, new_index)` event. Pin the npm version. Keyboard reordering must work
  (the library supports it). Fall back to "Nach oben" / "Nach unten" buttons in the panel.
- **Document:** every chapter is a bordered block with "<number> <title>" and the type
  badge, like the prototype. Unselected blocks render read-only from the stored content
  (prose as HTML, tables as tables, stories resolved from the map grouped by activity or
  slice, calc as bound values). Fixed frame entries render as greyed placeholder blocks with
  their heading and the note "Aus der Word-Vorlage".
- **Editing look (as in the prototype):** clicking a block selects it. The selected block
  gets the 2px accent border (`theme.ACCENT`) and keeps the same typography as the
  read-only view, so editing feels like typing in the document, not in a form. Only this
  block mounts its editor (one live editor at a time). Prose uses `mn.rich_text_editor` with
  `variant="subtle"` and its built-in toolbar hidden (`show_toolbar=False`); no editor
  chrome inside the block. The autosave contract stays as today (debounced
  `autosave(key, html)`, conflict handling).
- **Floating module toolbar:** a toolbar card hovers over the selected block: anchored to
  the block's top edge, overlapping the border by half its height, aligned right, with
  shadow, rounded corners and `theme` surface colors (macOS style). It is absolutely
  positioned inside the block wrapper and becomes `position: sticky` below the page header
  while the block scrolls, so it stays visible in long chapters. It appears with a short
  fade when the block is selected and disappears when another block or empty space is
  clicked. It never covers the chapter title. Formatting buttons drive the mounted Tiptap
  editor; if the appkit wrapper cannot take external toolbar controls, add a small wrapper
  that renders Mantine `RichTextEditor.Toolbar` outside the content area (check
  `appkit_mantine/tiptap.py` first; Mantine supports a toolbar placed anywhere inside the
  `RichTextEditor` root). Z-index stays below dialogs (`theme.PAGE_POPOVER_Z_INDEX`).
  CSS in `assets/css/aq-workshop.css`.
- **Toolbar content per module:** shown only on the selected block.
  - Text: bold, italic, H3, H4, lists, undo, redo, plus "KI: Kürzen", "Technischer",
    "Eigene Anweisung …".
  - Tabelle: add row, remove row, add or rename column, KI suggestion.
  - User Stories: group by Aktivität / Umsetzungsschnitt (segmented control), "Story Map öffnen".
  - Werte: add or remove bound value row (only from `BOUND_FIELDS`), link to the commercials.
- **Panel (right):** "Kapiteltyp · <type>", title as heading, editable "Überschrift",
  chapter description (the block's guiding question as help text), type specific settings
  (as in the prototype for stories), Leitfrage and Regeln, AI proposal diff with
  accept/reject, findings, history, protect switch, "Nach oben" / "Nach unten",
  "Entfernen" (red, hidden for required chapters, confirmation dialog).
- **"+ Kapitel" dialog:** two tabs, "Aus Bibliothek" (active blocks not yet in the offer,
  with type badge and description) and "Leeres Kapitel" (title + type). Inserts after the
  selected chapter.

## Phase 5: Admin menu "Angebote"
New page factory `create_offer_admin_page` in `components/alloq-offer/src/alloq_offer/admin/`
(`pages.py`, `states/`, `components/`), route `/admin/offers`, registered in `app/` like the
other admin pages, sidebar entry "Angebote" (icon `file-text`) in the `ADMIN` list. Tabs:
1. **Vorlagen:** list of templates; editor with the draft outline (same sortable component,
   add blocks from the library, set required, override title and level), Word layout upload
   (`.docx`, size limit from `WorkshopConfig.max_blob_bytes`, run `check_layout()` and show
   the German error, extract frame headings before and after the anchor), "Veröffentlichen"
   creates the next immutable version, version list with author and date.
2. **Kapitelbausteine:** list and editor of chapter blocks: key (only on create), title,
   type, level, default content (edited with the same block editors as in the offer),
   Leitfrage, Regeln (list), Prompt-Ergänzung, Pflichtangaben (`required_info`), Prüfungen
   (multi select of known checks). Shows which templates use the block. Deactivate instead of
   delete when in use.
3. **Prompts:** one entry per prompt name with the active text, edit creates a new version,
   version list with diff (reuse `content/text.diff_lines`) and "Aktivieren" to roll back.
   Warn that the text must keep the data-tag rules (`<map>`, `<briefing>`, …).
Every handler `requires_admin`; every write logs at `info` without content values.

## Phase 6: Docs
Update `spec/ki-angebotswerkstatt.md` (sections 5.5 and 6.1) and the matching page under
`docs/features/` for the new outline rules, the admin menu and template versions. Run the
`docs-sync` agent at the end.

---

## Tests (write first, per phase)
- Migration: `migration-reviewer` agent; a test that the seed payload parses into
  `TemplatePackage` and every `default_content` passes `parse_content`.
- `services/templates.py`: load by version, cache, unknown version error, layout check.
- Outline service: add from block and blank, remove required refused, soft delete and
  restore, move keeps frame and positions dense, numbering function (1, 2, 2.1, 3), conflict
  and protection rules, `requires_offer_editor` in `test_workshop_authorization.py`.
- Export snapshot and docx: order by position, removed chapters skipped, added chapter
  exported with its title and level.
- Draft job and findings use per-chapter `settings` and the chapter's prompt text; prompt
  version recorded as `name@version`.
- States: outline mixin handlers (select, reorder, add dialog, remove confirm), admin states
  (create block, publish template, upload invalid layout, prompt version activate), each
  refusing non-admins.
- Update existing tests that depend on YAML files (`test_workshop_template.py`,
  `test_workshop_chapters.py`, `test_workshop_chapter_state.py`, others found by grep for
  `load_template` and `chapters.yaml`).
- Coverage ≥ 80% for the new services and states.

## Success criteria
- `task format && task lint && task typecheck && task test` pass; no file over 1000 lines.
- Local visual check (chrome-devtools isolated context, local test login): the Kapitel tab
  matches the prototype layout; only the selected chapter shows its floating toolbar
  hovering over the block's top edge, and it stays visible while scrolling a long chapter;
  dragging a chapter
  in the outline reorders document and numbering and survives a reload; required chapters
  have no "Entfernen"; frame entries cannot be dragged; "+ Kapitel" adds a library block with
  its default content and a blank chapter.
- In `/admin/offers` an admin creates a block, adds it to a template, uploads a layout,
  publishes version 2; a new offer uses version 2, an existing offer still shows version 1.
- Editing the chapter prompt in admin changes the next AI chapter draft; the generation run
  shows the new prompt version.
- Word export of an offer with a moved and an added chapter has the right order, numbering
  and frame.
- The user runs the Alembic upgrade; Claude only hands over the command.

## Out of scope
- Story scope selection (the prototype's "Enthält Stories mit Scope" checkboxes). Scope was
  removed on purpose in the last commit; the stories panel only offers grouping.
- Moving the Branchen page into the new menu.
- Live multi-user editing in one chapter; the one-editor-per-chapter rule and conflict
  check stay.
- Migrating existing offers to a newer template version.
- New chapter types beyond prose, table, stories and calc.
