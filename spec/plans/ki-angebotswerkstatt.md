# Refined prompt: KI-Angebotswerkstatt in `alloq-offer` — multiphase plan (Etappe 0 + 1)

> Load `alloq-implementation` first in **every** phase, then `appkit-mantine-reference` before any `mn.*` component you have not used in this task, `reflex-state-and-architecture` / `reflex-testing-state` for states, `ai:building-pydantic-ai-agents` for the AI layer. Follow the test-first workflow and the definition of done of `alloq-implementation`. One phase = one reviewable PR. Do not start a phase before the previous one is green.

## Task

Build the AI-supported offer workshop described in `spec/ki-angebotswerkstatt.md` (German, 785 lines; read §5–§14, §17, §18 before each phase) **inside the existing package `components/alloq-offer`**. For an existing offer, an `offer_editor` adds customer sources (pasted text, EML, TXT, DOCX, PDF, PPTX, audio) and starts **one run that produces a complete first draft without further input**: extraction, a **User Story Map with simple stories (no acceptance criteria)**, the briefing, a scope proposal, all chapters of the bound Word template, rule checks plus AI review, and an editable DOCX draft in the existing QUO template layout. Afterwards the user only makes the decisions the AI must not make (confirm scope, resolve conflicts, confirm price) and may optionally refine the map on its own screen and the typed chapters in a Word-style document view before exporting a final DOCX.

### UI design (binding)

The UI **must follow the design "Kombination A + C – Entwurf in einem Durchlauf"** on the prototype canvas <https://claude.ai/artifact/SqvwnLbKttsfEL7XwnTcYX>. It has two clickable boards:

| Board | File on the canvas | Screen in Alloq |
| --- | --- | --- |
| A + C · 1 Entwurf erzeugen und Story Map anpassen | `project/Werkstatt.dc.html` | Tab "Entwurf & Story Map" (Phase 1 start card, Phase 3 progress and decisions, Phase 4 map editor) |
| A + C · 2 Kapitel im Dokument: Kapiteltypen | `project/Kapitel.dc.html` | Tab "Kapitel" (Phase 5 document view, Phase 6 findings, Phase 7 export panel) |

- Before building a screen, read its board (Artifact tool, action `read`, `url` above, `path` = the file in the table) and match its layout, texts, states and interactions. The boards are a layout and behavior reference, not code to copy: build with `mn.*` components, Alloq shell parts and `alloq_commons/theme.py` tokens.
- The first row of the canvas (concepts A, B, C) are earlier explorations. They are **not** the basis; where they differ from the A + C boards, the A + C boards win.
- Deviate from the boards only where Reflex/Mantine cannot do it the same way, and note each deviation in the phase's PR description.

The plan covers spec Etappe 0 (template proof) and Etappe 1 (first end-to-end version) in detail. Etappe 2/3 are only listed under "Out of scope".

## Decisions already made (do not re-ask)

| Topic | Decision |
| --- | --- |
| Placement | Extend `alloq-offer` (import `alloq_offer`). New code lives in a sub-package `alloq_offer/workshop/`. Depends only on `alloq-commons` + appkit, never on `app` or other alloq packages. |
| UI stack | Reflex + `appkit_mantine` (not Next.js as the spec suggests). Rich text via `mn.rich_text_editor` (Tiptap wrapper in `appkit_mantine/tiptap.py`). |
| UI design | Design "Kombination A + C – Entwurf in einem Durchlauf" (see "UI design (binding)" above). |
| LLM | Azure OpenAI through **pydantic-ai** (`OpenAIChatModel` + `AzureProvider`) behind a narrow port. Tests use pydantic-ai `TestModel` / `FunctionModel` via `Agent.override`, never the network. |
| Access | Whole workshop (sources, transcripts, map, chapters, findings, exports) read **and** write only for role `offer_editor` (`OFFER_EDITOR_ROLE`, `@requires_offer_editor`). Offer list stays readable for all. No per-offer ownership in Etappe 1. |
| Storage | A `BlobStore` protocol; first implementation stores bytes in Postgres (`offer_blobs`, `LargeBinary`, deduplicated by SHA-256) so server and desktop share files. Azure Blob is a later adapter. |
| Template | `Templates/QUO-33441-N7R0Z4_Preisindikation MVP Referenzdatenbank Treystar .docx` (styles `berschrift1..3`, 8 tables, 2 content controls, no Jinja tags yet). |
| Plan depth | Etappe 0 + 1 detailed. |
| First draft | **One click, end to end.** Job `initial_draft` chains: extract → map → briefing → scope proposal → all chapters → checks → Word draft. No manual gate between stages (spec §9.1). Optional setting "Automatisch entwerfen, sobald neue Quellen nutzbar sind". |
| Story map | **Its own screen** (prototype board A + C · 1, based on concept A): graphical card grid, editable. It is **not** part of the document or the Word export. |
| Document | Word-style document view (based on concept C) made of **typed chapters**: `stories`, `prose`, `table`, `calc`. The `stories` chapter shows the written stories from the map, never the map graphic. |

### Deliberate deviations from the spec

- Spec §6.1, §6.3, §11.1, §13.1 and A24 put the story map at the start of the Word document. **Decision: the map stays in the app only.** The document and the Word export contain the written stories (key, title, one sentence, scope) through a `stories` chapter. Rule checks and acceptance tests are adjusted accordingly (Phase 6, Phase 8).
- Spec §9.1 says the initial generation creates map and chapters without manual approval; this plan extends it to scope proposal, checks and the Word draft in the same run. A scope proposal never counts as offered scope until the user confirms it (A25 still holds).

## Context (found in the repo)

- **Offer package today** (`components/alloq-offer/src/alloq_offer/`): `entities.py` (89 l., `OfferEntity` table `offers`, `IndustryEntity`, `OfferStateEnum`), `models.py`, `repository.py` (`offer_repo`), `services/offers.py` (pure logic), `states/offer_state.py` (**578 lines** — do not grow it; workshop states are separate), `components/offer_*.py`, `pages.py` (`create_offers_page`, route `/offers`), tests in `components/alloq-offer/tests/` (one file per layer). Offers already carry `person_days`, `risk_buffer_days`, `production_cost`, `recommended_price` — reuse them as bound commercial values.
- **Access**: `alloq_commons/access.py` (`requires_offer_editor`, `requires_role` UI gate), `alloq_commons/roles.py` (`OFFER_EDITOR_ROLE` id 3). Background handlers cannot use decorators → inline role check inside `async with self` and list them in `INLINE_ADMIN_CHECK`-style lists of `tests/test_handler_authorization.py` (every new handler must be classified there; `alloq_offer` is in `OFFER_PACKAGES`).
- **Guards**: `tests/test_handler_authorization.py`, `tests/test_component_boundaries.py`, `tests/test_migrations.py` (one test per migration), `.claude/skills/alloq-implementation/scripts/check_file_sizes.py` (≤ 1000 lines; aim ≤ 400 per state).
- **Migrations**: head is `a2b3c4d5e6f7` (`alembic/versions/2026_10_22_offer_project.py`). Hand-written, `op.batch_alter_table`, named FKs/indexes, real `downgrade()`. Each new revision goes first in `KNOWN_REVISIONS` in `app/desktop/schema.py`. `alembic/env.py` must import the new entity module. **Never run alembic against the local profile** (it uses a shared remote DB) — the user applies migrations.
- **Async patterns**: only `@rx.event(background=True)` exists today (`alloq_dashboard/states/dashboard_states.py:170`, `alloq_project/states/project_validation_state.py:62`). `appkit_commons/scheduler/pgqueuer.py` is a cron-style scheduler, not a job queue — do not use it for workshop jobs.
- **Dependencies**: no LLM, docx, pdf, pptx or upload code installed. Add with `uv add --package alloq-offer <lib>` (CLAUDE.md: always `uv add`). `appkit_commons/ai/openai_client_service.py` exists but `openai` is not installed; prefer pydantic-ai's own Azure provider.
- **UI building blocks**: `alloq_commons/components/{shell.py (app_page), toolbar.py (window_toolbar, segmented, icon_button, primary_button), list_view.py, modal_layout.py}`, colors only from `alloq_commons/theme.py`, page popovers use `theme.PAGE_POPOVER_Z_INDEX`. `mn.dropzone` exists (unused so far). Static CSS goes to `assets/css/aq-*.css`.
- **Memory traps to respect**: list logic in big states → `rx.State, mixin=True`, never substates; keep DB code in place when splitting; `str(component)` escapes umlauts → assert on constants; `mn.number_input` on_blur sends formatted text; `rx.LocalStorage` lost on login; German names sort in Python, not SQL.
- **Docs**: feature docs live in `docs/features/` (see `offers.md`, `story-map.md`); diagram style per memory `docs-diagram-style`.

## Target layout (inside `components/alloq-offer/src/alloq_offer/workshop/`)

```
entities.py / models.py          # split into entities/ and models/ packages once > ~400 lines
repositories/                    # BaseRepository[XEntity, AsyncSession] + module singletons
storage.py                       # BlobStore protocol + DbBlobStore
jobs/                            # job entity helpers, claim/lease/retry, runner, handlers registry
extraction/                      # one parser per kind: text, eml, docx, pdf, pptx, audio
ai/                              # pydantic-ai agents, output schemas, prompt files, settings
services/                        # pure logic: map ops, story validation, scope, checks, diff, snapshot
content/                         # canonical content tree schema + editor HTML <-> tree converter
export/                          # template package loader, docx renderer, manifest
templates/quo_v1/                # chapters.yaml, rules.yaml, layout.docx (prepared copy)
states/                          # one state per tab; mixins for list logic
components/                      # sources, map, briefing, chapters, checks, export panels
pages.py                         # create_offer_workshop_page(sidebar) -> /offers/[offer_id]/werkstatt
```

UI text German; code, comments, logs English; `logger.debug` default, no f-strings in logger calls, never log source content or prompts (spec §15).

---

## Phase 0 — Template proof and content contract (spec Etappe 0, §6, §10.3, §13)

Goal: prove the QUO template can be filled with editable content before any AI work.

1. Inventory the QUO DOCX with a small script under `scripts/` (headings, styles, tables, numbering, TOC field, content controls, header/footer). Write the result to `docs/features/offer-workshop-template.md` (chapter list, which parts are static, which become generated, style names to use).
2. Define the **template package** `templates/quo_v1/`:
   - `chapters.yaml`: stable chapter keys, title, level, required flag, **chapter type** (`stories | prose | table | calc`), type defaults (e.g. scope filter and grouping for `stories`, columns for `table`, bound fields for `calc`), guiding question, content rules, order. Default order per inventory: management_summary (prose), user_stories (stories, scope `angeboten` + `option`, grouped by activity), loesung (prose), leistungsumfang (prose), mitwirkung (table: Mitwirkung · Verantwortlich · Zeitpunkt), rahmenbedingungen, projektabwicklung, laufzeit (prose), verguetung (calc), annahmen_risiken (prose or table). Static legal chapters (Rechtlicher Hinweis, Rechtliche Bestimmungen, Bindefrist, Unterschriften) stay fixed template text. There is no map chapter.
   - `layout.docx`: a prepared copy of the QUO file with `docxtpl` placeholders / subdoc anchors per chapter; customer data removed.
   - `rules.yaml`: per-chapter required info and checks (used in Phase 6).
   - A Pydantic `TemplatePackage` model + loader with a `version` string; compatibility check (every chapter key has an anchor in `layout.docx`).
3. Define the **chapter content model** (`content/schema.py`, Pydantic, discriminated union on `chapter_type`):
   - `prose`: the **canonical content tree** — `paragraph` (inline runs: text, bold, italic), `heading` (levels 3–4 only inside a chapter), `bullet_list`, `ordered_list`, `table` (header row + rows of plain inline runs), `bound_value` (reference to a structured field, e.g. `offer.recommended_price`). Every block has a stable `block_id`.
   - `table`: `columns` (labels) + `rows` (cells of plain inline runs); no merged cells.
   - `stories`: **no stored text**, only settings — `scopes` (subset of `offen|angeboten|option|ausgeschlossen`) and `group_by` (`activity|slice`). Content is resolved from the bound map revision at render time (key, title, "Als … möchte ich …, um …", scope label). Never acceptance criteria.
   - `calc`: an intro paragraph (prose runs) + a list of `bound_value` rows (label + field reference).
   Anything else is rejected with a German validation message.
4. Word renderer (`export/docx_renderer.py`) using `docxtpl` + `python-docx`: one renderer per chapter type (strategy registry keyed by `chapter_type`), mapping to template styles; `stories` renders a heading per group and one entry per story (key + title bold, scope label, sentence); `calc` renders a two-column table of resolved bound values (unconfirmed values as visible draft placeholder, never invented); adds no external resources. Unsupported content raises a typed error (no silent loss). The story map graphic is never rendered.
5. Reference export test: render a fixture with one chapter of each type, long text, nested lists, a wide table, umlauts/special chars (`<>&„“€`), many stories across activities; assert structurally with python-docx (chapter order, headings, table cells, styles, story sentences, TOC field present). Write the file to `tmp_path` and keep one sample under `docs/` for manual Word check.

Deps: `uv add --package alloq-offer docxtpl python-docx`.
Done: tests green; user opens the sample DOCX in Word and confirms layout (gate before Phase 3).

## Phase 1 — Workspace foundation, storage and job runner (spec §8.6, §14.2, §15)

1. Entities + one migration `2026_10_xx_offer_workshop_base.py` (down_revision `a2b3c4d5e6f7`):
   - `offer_workspaces` (offer_id unique FK → offers, RESTRICT because offers are never deleted; template_key, template_version, vision, roles JSON, map_revision int, story_seq int, doc_state `Entwurf|In Prüfung|Final`, created_by).
   - `offer_blobs` (sha256 unique, size, mime, data LargeBinary).
   - `offer_jobs` (offer_id, kind, status `queued|running|succeeded|failed|cancelled`, idempotency_key unique, payload JSON, input_revisions JSON, attempts, max_attempts, run_after, lease_until, error_class, error_message (technical text only), result JSON, timestamps). Index on (status, run_after).
2. `BlobStore` protocol (`put(bytes, mime) -> blob_id`, `get(blob_id)`, `delete`) + `DbBlobStore`; size limit from config.
3. Job runner (`jobs/`): `enqueue(kind, offer_id, payload, idempotency_key)` returns existing job for the same key; `claim_next()` uses `SELECT … FOR UPDATE SKIP LOCKED` on Postgres (plain select on SQLite tests); lease + heartbeat; bounded retries with backoff for transient errors; results of expired/cancelled jobs are discarded; model/parser calls run **outside** DB transactions. Handlers register by `kind` (registry pattern).
4. Worker: an async loop started via `app.register_lifespan_task` in `app/app.py`, enabled by config `offer_workshop.worker_enabled` (YAML + `__` env override), bounded concurrency. Desktop and server may both run it safely thanks to SKIP LOCKED.
5. Config section in `configuration/config.yaml` for workshop (limits, worker, Azure OpenAI endpoint/deployments, secret refs `secret:azure_openai_api_key`), loaded via appkit config pattern (`appkit-commons` skill).
6. Page shell: `create_offer_workshop_page(sidebar)` route `/offers/[offer_id]/werkstatt`, gated with `requires_role(…, OFFER_EDITOR_ROLE.name)`; tabs `Entwurf & Story Map · Kapitel · Briefing · Export` (sources live in the right panel of the first tab, findings in the chapter view, as in the prototype); entry from the offer inspector ("Werkstatt öffnen", offer_editor only). Opening creates the workspace lazily with the default template package. Without a draft the first tab shows the start card ("Entwurf aus N Quellen erzeugen", auto-draft setting, what the AI looks for) and never invented content (spec §5.1).
7. Tests: repository, job claim/retry/lease/idempotency (SQLite), state open/create workspace, authorization classification, migration test, `KNOWN_REVISIONS`.

## Phase 2 — Sources and extraction (spec §5.2, §7)

1. Entities + migration: `offer_sources` (offer_id, kind `text|eml|txt|docx|pdf|pptx|audio`, title, filename, mime, blob_id, sha256, version, replaces_id, status `hochgeladen|in Verarbeitung|nutzbar|teilweise nutzbar|fehlgeschlagen|manuell nötig`, status_detail, included bool, revoked_at), `offer_source_blocks` (source_id, seq, anchor JSON {page|paragraph|table|slide|shape|note|start_ms/end_ms|message_id}, kind, speaker, text, gap flag + reason).
2. Upload via `mn.dropzone` / `rx.upload` (type and size whitelist, no macros executed, macro-enabled Office types rejected) and a "Text einfügen" modal. Identical sha256 on the same offer → no new version, no new job. Replacing a file creates a new version.
3. Parsers (`extraction/`, one module each, pure `bytes -> ExtractionResult`):
   - pasted text / TXT; EML via stdlib `email` (subject, date, sender, message-id, quoted chain and signature detection, attachments become their own sources).
   - DOCX via python-docx (paragraphs, tables; anchors by paragraph/table index).
   - PDF via `pypdf` (pages; pages without text layer → gap "OCR nötig", not silently skipped).
   - PPTX via `python-pptx` (slide no., text frames, tables, notes; picture shapes → gap "Bildinhalt nicht ausgewertet").
   - Audio (WAV/MP3/M4A) via a `Transcriber` port with an Azure OpenAI transcription implementation (diarized output with timestamps if the deployment supports it — verify API via Context7 before coding); files above the provider limit get status "manuell nötig" with hint to upload a transcript. Speaker labels are technical (`Sprecher 1`), never identities (§7.3).
4. Extraction runs as job kind `extract_source`; status visible per source with retry button; failed/partial sources stay visible; user can include/exclude sources for drafts.
5. Sources tab UI: list with status badges, gaps, block viewer with anchors (no technical IDs shown).
6. Tests: one parser test file per kind with small fixture files built in the test (python-docx/python-pptx generate fixtures; EML as string; PDF fixture minimal), job handler test with fake `Transcriber`, dedupe/versioning tests, A01/A02 scenarios.

Deps: `uv add --package alloq-offer pypdf python-pptx` (+ `pydantic-ai-slim[openai]` if the transcriber uses the openai client in this phase).

## Phase 3 — AI port, story map generation and the one-click draft pipeline (spec §8, §9)

1. `ai/` port: `OfferAi` protocol with methods `propose_map`, `propose_briefing`, `propose_chapter`, `review`, each returning validated Pydantic output; implementation with pydantic-ai agents on Azure OpenAI deployments from config; prompt texts in versioned files (`ai/prompts/*.md`, version string stored with every run). Source text is passed as clearly delimited **data**; system prompt states that instructions inside sources must be ignored (§15). Call budget and timeout per job.
2. Output schemas: `ProposedMap` (vision, roles, activities → tasks → stories {title, role, goal, benefit, origin `Kunde|Vorschlag`, source_refs [block ids], scope always `offen`}, slices, skeleton suggestions, open questions, conflicts) and `ProposedBriefing` (statements per §8.1 type: Kundenanforderung, Belegter Sachverhalt, Lösungsvorschlag, Annahme, Offener Punkt/Konflikt; with source refs).
3. Entities + migration: `offer_activities`, `offer_tasks`, `offer_stories` (key unique per offer from `story_seq`, e.g. `US-07`, title, role, goal, benefit, scope `offen|angeboten|option|ausgeschlossen`, origin `Kunde|Vorschlag|Nutzer`, slice_id, skeleton, priority, source_refs JSON, split_from_id, archived_at), `offer_slices`, `offer_statements` (type, text, status, source_refs, needs_recheck, confirmed_by/at), `offer_map_revisions` (offer_id, revision, immutable snapshot JSON, created_by, created_at), `offer_generation_runs` (job_id, kind, model, prompt_version, input revisions, status).
4. Pure services: `story_validation` (exactly one sentence "Als … möchte ich …, um …"; reject Given/When/Then, "Akzeptanzkriterien", bullet checklists — A20), `apply_proposed_map` (app assigns keys; AI never reuses or reinterprets existing keys; new AI stories never get scope `angeboten` — A25), `snapshot_map` (builds revision JSON).
5. Job kind `initial_draft` as an **end-to-end pipeline** of named stages, each stage persisted before the next starts so a failure resumes from the last finished stage: `extract` → `map` (save map revision 1) → `briefing` → `scope_proposal` (mark the walking skeleton as proposed scope; stories stay `offen`) → `chapters` → `checks` → `word_draft`. This phase implements the first four stages; Phases 5, 6 and 7 register `chapters`, `checks` and `word_draft` in the same pipeline (stage registry, so a missing stage is skipped and reported, not faked). Progress per stage is visible in the UI ("Entwurf wird erstellt …" list). Auto-draft: when the workspace setting is on and a source becomes usable, enqueue `initial_draft` (or, if a draft exists, a map-update **proposal**, never an overwrite).
6. Derive the **decision list** from the draft: confirm proposed scope, open conflicts from the briefing, unconfirmed commercials (only blocking for final). Stored as findings with type `decision` so Phase 6 can reuse them.
7. Tests: agent tests with `FunctionModel` returning fixed JSON; validation rejects acceptance criteria; keys stable; pipeline resumes after a failed stage and skips unregistered stages visibly; A19, A20, A21 (no knowledge base), A22 (variants kept as open questions), A25, A26.

Deps: `uv add --package alloq-offer "pydantic-ai-slim[openai]"`.

## Phase 4 — Story map, story and briefing editors (spec §5.3, §5.4, §8.3–8.5, §10.1–10.2)

1. **"Entwurf & Story Map" screen** (own screen, prototype board A + C · 1; the map never appears in the document):
   - Start card before the first draft (see Phase 1); progress list of pipeline stages while `initial_draft` runs (state polls job status via a background event).
   - After the draft: summary card (counts of activities, stories, drafted chapters, Word draft revision; buttons "Kapitel ansehen", "Word-Entwurf herunterladen") and the **"Braucht deine Entscheidung"** list from Phase 3 ("Umfang bestätigen" sets all proposed skeleton stories to `angeboten` in one action; conflict and calculation link to their places).
   - Graphical map grid: activity columns with inline-editable title and task, ‹ › to reorder, ✕ to remove only when empty, "+ Aktivität"; slice rows with inline-editable names and "+ Umsetzungsschnitt"; story cards colored by scope (colors from `theme.py`), `S` marker for the walking skeleton, dashed cards for AI suggestions with "Übernehmen / Verwerfen" (key assigned only on accept); "+ Story" in every cell. No drag and drop in Etappe 1.
   - Story inspector (right panel, replaces the sources panel while a story is selected): title, Als / möchte ich / um fields with live sentence preview and a hint when a part is missing, scope segmented control, activity and slice selects, origin and source anchors, "Aufteilen", "Archivieren".
   - Sources panel (right panel when nothing is selected): drop zone, per-source status and gaps, include checkbox per source.
2. Every map write uses optimistic concurrency: handler sends expected `map_revision`; mismatch → German conflict toast + reload, no overwrite (A08). Each saved change bumps `map_revision` and writes a snapshot; split keeps `split_from_id`; archived keys are never reused (A23).
3. Briefing tab: statements grouped by type, conflicts show both source anchors (A03), "Als fachliche Entscheidung bestätigen" is a separate explicit action (§8.7, A17).
4. Story/scope change marks dependent chapters `needs_review` (hook ready for Phase 5; A09, A27) and shows the banner "Map geändert … Kapitel neu vorschlagen", which enqueues chapter proposals for affected `prose` chapters; `stories` chapters update automatically because they are resolved from the map revision.
5. Map-level AI actions as jobs returning a **proposal** (compare + accept), e.g. "fehlende Prozessschritte vorschlagen", "Story aufteilen". Proposals bound to an older revision are shown as "veraltet" (A07).
6. Keep states ≤ ~400 lines: `MapState` + `MapEditMixin` + `StoryDrawerState`, list logic in mixins. Tests per handler incl. conflict and authorization.

## Phase 5 — Chapters, editor, revisions and proposals (spec §5.5, §9.4, §10.2–10.4)

1. Entities + migration: `offer_chapters` (offer_id, chapter_key, **chapter_type** `stories|prose|table|calc`, position, title, required, protected, needs_review, review_reason, current_revision_id), `offer_chapter_revisions` (chapter_id, number, content JSON = typed content from Phase 0, base_revision, map_revision, origin `manuell|KI übernommen`, author), `offer_proposals` (target chapter or map, job_id, content JSON, base revision, status `offen|übernommen|verworfen|veraltet`). The chapter type is fixed after creation.
2. Converter `content/editor_io.py` for `prose`: `mn.rich_text_editor` value ↔ canonical tree, restricted to the Phase 0 block set (check in `appkit-mantine-reference` whether the editor emits HTML or JSON; parse HTML with stdlib `html.parser`, drop nothing silently — unsupported markup → validation finding). Round-trip tests for every block type (A06). Editor toolbar limited to the supported marks. `table` cells use plain inputs; `stories` and `calc` have no free-text editing of their resolved parts.
3. **"Kapitel" screen** (Word-style document view, prototype board A + C · 2):
   - Left: outline with chapter number, title and a type badge (`Stories`, `Text`, `Tabelle`, `Werte`); static template chapters shown greyed; "+ Kapitel".
   - Center: the offer as one page-like document; each chapter renders by type — `prose` editable in place, `table` with editable cells and "+ Zeile", `stories` as written stories grouped under headings (key, title, scope pill, one sentence), `calc` as a table of bound values with unconfirmed values marked. Selected chapter is outlined.
   - "+ Kapitel einfügen" opens a type menu (Fließtext, Tabelle, User Stories, Kalkulation) and inserts the new chapter after the selected one with type defaults from `chapters.yaml`.
   - Right: settings of the selected chapter by type — heading; `stories`: scope checkboxes and group-by (Aktivität / Umsetzungsschnitt) plus link "Story Map öffnen"; `prose`: "Vor KI-Änderungen schützen", AI actions (neu entwerfen, kürzen, technischer); `table`: columns, add row; `calc`: confirmation state, link to the calculation. Move up/down, remove (not for required chapters). Findings and export below.
4. Autosave with expected base revision (debounced); visible save state; conflict → visible message, no overwrite (A08). Revision history with diff and restore.
5. Pipeline stage `chapters` (registered in `initial_draft`) and job kind `draft_chapters` for later redrafts: uses map revision + briefing + template guiding questions + profile (Software/AI/Agent/Data Science, §12.2). The AI writes only `prose` content and `table` rows; `stories` and `calc` chapters are filled by the app from map and commercial fields, never by the model. In the initial run drafts are saved directly as revision 1; later runs produce proposals and never overwrite a manual or protected chapter (A07). "Vorschlag übernehmen" creates a new revision; it does not confirm business decisions (A17).
6. Tests: converter round-trip, per-type validation, insert/move/remove rules, stories resolution with scope filter and grouping, revision conflict, stale proposal, protected chapter, needs_review after story change.

## Phase 6 — Commercial values, rule checks and AI review (spec §8.7, §11, §12.1)

1. Commercial fields: reuse offer fields (`person_days`, `risk_buffer_days`, `production_cost`, `recommended_price`) plus new workspace fields (currency, validity date, price required flag) and an explicit "Kalkulation bestätigen" action storing confirmed_by/at and the confirmed values. Chapters reference them only via `bound_value` blocks. Changing a confirmed value invalidates the confirmation and marks linked chapters (A09).
2. Entities + migration: `offer_findings` (offer_id, rule, severity `Blocker|Warnung|Hinweis`, source `Regel|KI`, target, revision refs, message, decision `offen|behoben|akzeptiert`, reason, decided_by/at).
3. Rule checks as pure functions over a snapshot (§11.1): required chapters present, at least one `stories` chapter that contains every `angeboten` story and no acceptance criteria, every story assigned to task/activity, map/story revision matches chapters, no placeholders, statuses on requirements, price/sum consistency, free-text numbers that differ from bound values (A18), sources still allowed (revoked source → finding).
4. AI review (§11.2) as pipeline stage `checks` and as an on-demand job → findings with concrete reference, never edits content, no global score. A fix the AI suggests is a proposal on the chapter (accept / reject inline in the document view).
5. Findings appear in the right panel of the chapter view and as markers in the outline; decision with mandatory reason where the rule allows acceptance. No separate Prüfung tab.
6. Tests: each rule with pass/fail fixtures; A04, A05, A11, A15, A18.

## Phase 7 — Snapshots and Word export (spec §5.6, §11.3, §13)

1. Entities + migration: `offer_snapshots` (immutable JSON of the map revision used to resolve `stories` chapters, the resolved stories, typed chapters in order, bound values, template version), `offer_exports` (snapshot_id, kind `Entwurf|Final`, template_version, exporter_version, blob_id, sha256, status, error, created_by).
2. Export flow as job `export_docx`: unsaved browser changes block export; server builds snapshot → validates kind (final requires: required chapters, no open blockers, confirmed commercials if the template demands a price, user confirmation of the whole snapshot) → renders with Phase 0 renderer → structural check → stores blob + manifest. Draft shows a visible draft marker and open points; final hides internal review metadata but keeps customer-relevant assumptions, exclusions and obligations (§11.3).
3. Pipeline stage `word_draft` (registered in `initial_draft`) creates the first draft export automatically. Export tab: list of exports with kind, revision, date, author; download returns the stored bytes exactly (`rx.download`); failure keeps state and shows retry (A13). No sync back from Word (A16).
4. Template binding: workspace stores template version; a new package version does not change existing offers (A14).
5. Tests: final blocked with reasons (A11), draft allowed, manifest checksum, download equals stored blob, A12, A24 as adjusted (Word contains the written stories of the same map revision as the chapters; no map graphic).

## Phase 8 — Hardening, docs and acceptance matrix (spec §14.2, §15, §18, §19)

1. Source revocation/deletion: blocks further use immediately, marks dependent content, deletes blobs and blocks (§15).
2. Telemetry: job durations, status, error classes, token/cost counters per phase in logs (no content, no prompts).
3. Authorization sweep (A10): every workshop handler and download path checks `offer_editor`; non-editors get no workspace data, not even via direct URL.
4. Acceptance matrix: `components/alloq-offer/tests/test_workshop_acceptance.py` mapping A01–A27 to tests (or to the phase test that covers them); list any case not automatable. Record the adjusted reading of A19/A24 (map is the first artifact in the app, not in Word) and add a case "one click from usable sources to a Word draft without further input".
5. Docs: `docs/features/offer-workshop.md` (user flow, stories, architecture diagram per `docs-diagram-style`), update `docs/features/offers.md` and `README.md`. Memory updates for new traps.

## Cross-phase requirements

- Tests first; coverage ≥ 80 % for non-Reflex classes and states; `task format && task lint && task typecheck && task test` green after each phase; `tests/test_handler_authorization.py` run after every handler change; file size check.
- Every migration: hand-written, tested in `tests/test_migrations.py`, added first to `KNOWN_REVISIONS`, imported in `alembic/env.py`. The user applies migrations; do not run alembic against `PROFILES=local`.
- Secrets only via config secret refs / Key Vault; `SecretStr.get_secret_value()`.
- No content, prompts or credentials in logs; parameterized logging only.
- Stories never get acceptance criteria — at generation, regeneration, review and export.

## Success criteria (end of Phase 8)

- With `worker_enabled` and an Azure OpenAI deployment configured, an `offer_editor` can: open the workshop from an offer, add an EML, a DOCX, a PDF, a PPTX and an audio file, see per-source status and gaps, and with **one click** get story map, briefing, scope proposal, all chapters, findings and a downloadable Word draft without further input. They can then confirm the scope, resolve the listed decisions, optionally edit the map on its own screen and the typed chapters in the document view, and download a final DOCX that opens in Word with the QUO layout, the written stories and editable chapters (no map graphic).
- A user without `offer_editor` cannot reach any workshop data.
- All A01–A27 cases are covered by tests or documented manual checks.

## Out of scope (Etappe 2/3 and later)

Company knowledge base / Azure AI Search, effort estimation by AI, more templates and profiles beyond quo_v1, MSG files, mailbox/meeting/SharePoint/CRM connectors, OCR and visual slide analysis (Etappe 1 only flags these gaps), drag and drop map editing, live collaboration, per-offer member permissions, Word preview and Word re-import, Azure Blob adapter, four-eyes approval.
