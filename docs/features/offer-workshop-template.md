---
title: Offer workshop template (QUO)
description: How the QUO price indication template is split into a fixed layout and typed, generated chapters for the KI-Angebotswerkstatt, how admins publish new template versions and edit chapter blocks and prompts, and which styles the Word export uses.
story_ids: []
source_paths:
  - alembic/versions/2026_10_31_offer_templates.py
  - alembic/versions/2026_11_01_offer_template_layout_clean.py
  - alembic/seed/quo_v1_layout.docx
  - components/alloq-offer/src/alloq_offer/workshop/template_entities.py
  - components/alloq-offer/src/alloq_offer/workshop/services/templates.py
  - components/alloq-offer/src/alloq_offer/workshop/services/template_drafts.py
  - components/alloq-offer/src/alloq_offer/workshop/services/chapter_blocks.py
  - components/alloq-offer/src/alloq_offer/workshop/services/prompts.py
  - components/alloq-offer/src/alloq_offer/admin/
  - components/alloq-offer/src/alloq_offer/workshop/export/template_package.py
  - components/alloq-offer/src/alloq_offer/workshop/export/docx_renderer.py
  - components/alloq-offer/src/alloq_offer/workshop/content/schema.py
  - scripts/inventory_docx.py
  - scripts/build_quo_layout.py
---

# Offer workshop template (QUO)

The workshop fills the customer template `Templates/QUO-33441-N7R0Z4_Preisindikation MVP Referenzdatenbank Treystar .docx`.
`scripts/inventory_docx.py` prints its structure; `scripts/build_quo_layout.py` turns it into the layout.
The template lives in the database: the migration `2026_10_31_offer_templates.py` seeds template `quo_v1` as published version 1, with its chapter blocks, the five AI prompts as version 1 and the layout from `alembic/seed/quo_v1_layout.docx` as a blob. The migration `2026_11_01_offer_template_layout_clean.py` replaces a layout stored by an earlier, uncleaned seed with the cleaned file.

## What is fixed and what is generated

| Part | Source in the QUO file | In the package |
| --- | --- | --- |
| Cover (title, customer, date, quote id) | paragraphs 0 to 25 | the layout with `{{ project_title }}`, `{{ customer_name }}`, `{{ customer_street }}`, `{{ customer_city }}`, `{{ customer_short }}`, `{{ offer_date }}`, `{{ quote_id }}` |
| Legal notice, supplier address | cover | fixed text |
| Table of contents | missing in the QUO file | TOC field `1-3`, updated when Word opens the file |
| Chapters Management Summary to Consumption | Heading 1 to 3 | removed from the layout, rendered from typed chapters at the anchor `[[KAPITEL]]` |
| Rechtliche Bestimmungen, Bindefrist (`{{ validity_date }}`), Sonstiges, Anlagen, Unterschriften | tail | fixed text; signature placeholders (`$$_PRT_..._$$`) stay untouched |

Customer data, reviewer comments, people, labels and author names are removed from the layout. There is no story map chapter: the document shows written stories only.

## Chapters of version 1

| Key | Level | Type | Required |
| --- | --- | --- | --- |
| `management_summary` | 1 | prose | yes |
| `leistungen` | 1 | prose | no |
| `user_stories` | 2 | stories (all live stories, grouped by activity) | yes |
| `loesung` | 2 | prose | yes |
| `leistungsumfang` | 2 | prose | yes |
| `mitwirkung` | 2 | table (Mitwirkung, Verantwortlich, Zeitpunkt) | yes |
| `rahmenbedingungen` | 2 | prose | no |
| `projektabwicklung` | 1 | prose | no |
| `laufzeit` | 1 | prose | yes |
| `verguetung` | 1 | calc (person days, risk buffer, production cost, recommended price) | yes |
| `annahmen_risiken` | 1 | prose | no |

The consumption chapter of the QUO file is not part of Etappe 1.

## Versions and the admin menu "Angebote"

Admins manage templates, chapter blocks and AI prompts on the page `/admin/offers` ("Angebote" in the administration). The page and every handler on it are admin only. The workshop itself stays closed to admins without the role `offer_editor`.

| Tab | What admins do |
| --- | --- |
| Vorlagen | Edit the draft outline of a template: add a block, remove an entry, drag entries into order, and set title, level and the required flag per entry. Upload a Word layout. Publish the draft as the next version. |
| Kapitelbausteine | Create and change chapter blocks: key, title, type, level, guiding question, content rules, prompt text, required information, checks and start content. Deactivate a block, or delete it while no template uses it. |
| Prompts | Save a new version of an AI prompt or activate an older one. Each version shows its author, its time and the lines changed against the version before. |

**Versions.** A template has one draft and any number of published versions. Publishing copies the outline, every block setting and the layout into a new version that never changes again. Publishing a draft that equals the latest version is refused. A new offer binds the latest version when its workspace is created, and copies the outline into its own chapters. Existing offers keep their version and their chapters. Offers stored with the old version text `quo_v1.0` count as version 1.

**Layout upload.** The file must be a `.docx` with exactly one paragraph `[[KAPITEL]]`. Headings before and after the anchor are the fixed frame. Before the file is parsed, its size as a zip is checked: at most 2000 parts, 10 MB per XML part and 100 MB unpacked in total. The stored layout is cleaned of comments, people, custom XML, custom and extended properties, the thumbnail, linked files, tracked changes (deleted and moved-away text, old formatting) and author, subject and print data. Layouts are cleaned again when a version is loaded. A replaced draft layout is deleted when no published version uses it.

**Prompts.** Each prompt name has numbered versions and exactly one active version. The AI loads the active version once per run and records it as `name@version` in the generation run. A fixed rule about the data tags of that prompt (`DATA_TAGS` in `services/prompts.py`, for example `<map>`, `<briefing>` and `<aktueller_text>` for chapters) always comes before the prompt text and cannot be removed in the admin menu. Admins are trusted. A prompt text that contradicts this rule weakens it, so the tab shows a warning above the text.

## Word styles used by the renderer

| Content | Style |
| --- | --- |
| Chapter titles | `Heading 1` and `Heading 2` (style ids `berschrift1`, `berschrift2`) |
| Headings inside a chapter | `Heading 3`, `Heading 4`, never above the chapter level |
| Text | `Normal` |
| Bullet list | `Aufzählung 1` |
| Ordered list | `List Number` |
| Tables | table style `arvato-Tabelle blau`, header row repeats |

## Rendering rules

- Content is rendered by one renderer per chapter type; unknown content raises a typed error and is never dropped.
- `stories` chapters list the stories of the bound map revision: a heading per group, then key and title, then the one sentence "Als … möchte ich …, um …".
- `calc` values are shown only when confirmed; an unconfirmed value carries `[nicht bestätigt]`, a missing one `[Wert fehlt]`.
- A draft export starts with the marker "ENTWURF – nicht zur Weitergabe an den Kunden".
- `docs/features/offer-workshop-sample.docx` is a reference export for the manual check in Word.
