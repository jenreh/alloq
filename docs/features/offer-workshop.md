---
title: Offer workshop
description: How an offer editor turns customer sources into a story map, chapters, checks and an editable Word offer on the page "Angebotswerkstatt", and how the workshop is built.
source_paths:
  - components/alloq-offer/src/alloq_offer/workshop/
  - alembic/versions/2026_10_23_offer_workshop_base.py
  - alembic/versions/2026_10_28_offer_exports.py
  - alembic/versions/2026_10_31_offer_templates.py
  - alembic/versions/2026_11_01_offer_template_layout_clean.py
last_verified_commit: "unreleased offer workshop"
---

# Offer workshop

The workshop is the page `/offers/<id>/werkstatt` ("Angebotswerkstatt"). It belongs to the package `alloq-offer`, lives in `alloq_offer/workshop/` and is open only to the role `offer_editor`. Other roles, administrators included, get no workshop data and cannot run any workshop action. The tests `test_workshop_authorization.py` and `tests/test_handler_authorization.py` enforce this for every handler.

The planning background is in [spec/ki-angebotswerkstatt.md](../../spec/ki-angebotswerkstatt.md). The Word template, its versions and the admin menu "Angebote" for templates, chapter blocks and prompts are described in [Offer workshop template](./offer-workshop-template.md). Offers themselves are described in [Offers](./offers.md).

## User flow

1. **Open the workshop** from an offer. The workspace is created on the first visit and bound to the current template version.
2. **Add sources** in the tab "Entwurf" (right column): pasted text, EML, TXT, DOCX, PDF, PPTX and audio. Each source shows its status and its gaps, a progress bar shows how many sources are read, and "Ansehen" lists the extracted blocks with their place (page, paragraph, slide, time) (scanned pages, pictures, audio that needs a transcript). Identical content adds nothing, changed content with the same file name becomes a new version. A source can be withdrawn; see below.
3. **Create the first draft.** One click on "Entwurf aus N Quellen erzeugen" runs a chain of jobs: story map and briefing, then every prose chapter (kept as revision), then the AI review and the first Word draft. With "Automatisch entwerfen" the chain starts by itself once a source is usable; with an existing map a new source only gives a map proposal. The tab "Entwurf" shows each stage with a progress bar, then a summary with the download of the Word draft and the list "Braucht Ihre Entscheidung" (open points in the briefing, calculation, blockers). Stories are simple sentences "Als ..., möchte ich ..., um ..." and never carry acceptance criteria. Every live story on the map is part of the offer; to leave a story out, archive it.
4. **Edit the map** in the tab "Story Map". Add, rename, reorder, split and archive activities, tasks and stories and move stories between slices. Every write names the map revision it expects; a stale write is refused and the current map is shown. The AI can also propose missing process steps or a split of the selected story. Such a proposal is shown as a comparison, is bound to the map revision it was made for, becomes "veraltet" when the map changed, and adds only new elements when taken over.
5. **Read the briefing.** Statements are grouped by type. Conflicts show both sources. "Als fachliche Entscheidung bestätigen" is a separate, explicit action.
6. **Write the chapters.** The tab "Kapitel" shows the offer as one document with an outline on the left and a panel for the selected chapter on the right. Only the selected chapter shows its toolbar, which floats over the chapter's top edge. The outline follows the rules in "Outline" below. The editor saves automatically against the revision it started from. Each save is a new revision with history, diff and restore. AI proposals appear as a comparison and change nothing until a person accepts them. A protected chapter is never changed by the AI.
7. **Check.** Rule checks run when the tab opens. The AI review adds remarks, but never edits content and cannot raise a blocker. Blockers cannot be accepted, other findings only with a reason.
8. **Confirm the calculation.** The values come from the offer. Any later change voids the confirmation and flags the chapters that show the values.
9. **Export.** The tab "Export" creates a Word draft at any time, and a final version once no blocker is open, the calculation is confirmed (when a price is required) and the person confirms the whole state. Each file is made from a fixed snapshot. Changes made later in Word are not taken back into the workshop.

## Outline

Each offer has its own outline, copied from the template version it is bound to.

- **Add.** "+ Kapitel" adds a block from the library with its start content and settings, or a blank chapter of type prose, table, stories or calc. A block can be in the outline only once. An offer has at most 100 chapters.
- **Remove and restore.** Required chapters cannot be removed. A removed chapter keeps its revisions, findings and proposals and can be restored. A restored chapter goes to the end of the outline and is flagged for review. Findings of removed chapters are not shown until the chapter comes back.
- **Order.** Chapters are dragged in the outline, by mouse or by keyboard (space to pick up, arrow keys to move, space to drop). The fixed frame of the layout is not part of the outline and never moves.
- **Title and level.** Each chapter can be renamed and set to level 1 (Kapitel) or 2 (Unterkapitel). The first chapter always has level 1. The numbers (1, 2, 2.1, 3) follow position and level, in the workshop and in Word.
- **Export.** Word shows the chapters in outline order with their titles and levels. Removed chapters are left out.

All outline changes need the role `offer_editor` and are refused for archived offers.

## Output kinds

| Kind | Allowed when | Content |
| --- | --- | --- |
| Entwurf | Always | Visible draft marker, open points at the end |
| Final | No open blocker, confirmed calculation if a price is required, confirmation of the whole state | No draft marker, no internal review notes |

## Source withdrawal

Withdrawing a source (trash button in the source list) blocks its use at once. The extracted blocks and the stored file are deleted, the file only when no other source uses the same content. All versions of the same file are withdrawn together. Briefing statements that cite the source get the mark "needs recheck", the written chapters are flagged for review, and the check `source_revoked` lists every story and statement that still cites the deleted blocks.

## Architecture

| Layer | Where | Notes |
| --- | --- | --- |
| Entities and migrations | `workshop/entities.py`, `alembic/versions/2026_10_2*` | One migration per phase; the user applies them |
| Storage | `workshop/storage.py` | `BlobStore` port, files in Postgres once per SHA-256 |
| Jobs | `workshop/jobs/` | Own persistent queue with lease, retries and idempotency keys; handlers register by kind |
| Extraction | `workshop/extraction/` | One pure parser per source kind |
| AI | `workshop/ai/` | pydantic-ai agents on Azure OpenAI behind a port, versioned prompts, sources passed as delimited data |
| Services | `workshop/services/` | Map, chapters, checks, findings, commercials, snapshots, exports, source withdrawal |
| Content | `workshop/content/` | Canonical content tree and editor conversion; unsupported markup is reported, not dropped |
| Export | `workshop/export/` | Template package of a published version (`services/templates.py`), Word renderer, structural check |
| Outline | `services/outline.py`, `services/numbering.py` | Add, remove, restore, move, rename and re-level chapters; numbering |
| Admin | `alloq_offer/admin/`, `services/template_drafts.py`, `services/chapter_blocks.py`, `services/prompts.py` | Page `/admin/offers` with the tabs Vorlagen, Kapitelbausteine and Prompts |
| States and components | `workshop/states/`, `workshop/components/` | One state per tab |

Jobs run in the worker task started with the app when `app.offer_workshop.worker_enabled` is true. Without it, uploaded sources stay "hochgeladen" and no draft or export is made. Server and desktop can both run it, because jobs are claimed with `FOR UPDATE SKIP LOCKED`.

The chain of the first draft lives in `services/draft_pipeline.py`. Each stage is its own job, so a failed stage is retried alone and the stages before it stay saved.

`app.offer_workshop.ai_provider` selects the model: `azure` (default) or `demo`. The demo provider (`ai/demo.py`) needs no language model: stories, statements and chapter text quote sentences of the sources and cite their blocks. The local profile uses it together with the worker. `scripts/seed_workshop_demo.py` creates a complete demo offer with five sources in the configured database.

### Export flow

1. The state refuses the request while the chapter editor shows an unsaved or conflicting change.
2. The service runs the rule checks on the current state and, for the final version, collects every reason (open blockers, unconfirmed calculation, missing confirmation).
3. It stores an immutable snapshot (chapters with their revision numbers, resolved stories and values, cover data, open points) and queues the job `export_docx`.
4. The job renders the snapshot with the template version stored in the snapshot, checks the file (chapter headings in order, draft marker fits the kind), stores it and writes the manifest: snapshot, map revision, template and exporter version, chapter revisions, checksum, size.
5. The download returns exactly the stored bytes and refuses a file whose checksum changed. A failed job leaves the export marked as failed with a retry by a new request; the saved offer is untouched.

A template version that is no longer available stops the export with a clear message, so an offer keeps its bound version until it is migrated on purpose.

## Operations

- Telemetry: the worker logs one line per job attempt with kind, outcome, duration and error class, and one line per model call with the number of requests and tokens. Source text, prompts and chapter content are never logged.
- Configuration: see `WorkshopConfig` in `workshop/configuration.py` (limits, worker, Azure OpenAI). The API key is a secret reference.
- Tables: `offer_workspaces`, `offer_blobs`, `offer_jobs`, `offer_sources`, `offer_source_blocks`, `offer_activities`, `offer_tasks`, `offer_stories`, `offer_slices`, `offer_statements`, `offer_map_revisions`, `offer_generation_runs`, `offer_chapters`, `offer_chapter_revisions`, `offer_proposals`, `offer_findings`, `offer_snapshots`, `offer_exports`, `offer_chapter_blocks`, `offer_templates`, `offer_template_chapters`, `offer_template_versions`, `offer_prompts`.

## Tests

`components/alloq-offer/tests/test_workshop_acceptance.py` maps the acceptance cases A01 to A27 of the spec to the tests that prove them and fails when a proof disappears. One check cannot be automated: open an exported file in Word and look at layout, table of contents (fields update on open), headers and footers.
