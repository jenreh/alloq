---
title: Offer workshop template (QUO)
description: How the QUO price indication template is split into a fixed layout and typed, generated chapters for the KI-Angebotswerkstatt, and which styles the Word export uses.
story_ids: []
source_paths:
  - components/alloq-offer/src/alloq_offer/workshop/templates/quo_v1/chapters.yaml
  - components/alloq-offer/src/alloq_offer/workshop/templates/quo_v1/rules.yaml
  - components/alloq-offer/src/alloq_offer/workshop/templates/quo_v1/layout.docx
  - components/alloq-offer/src/alloq_offer/workshop/export/template_package.py
  - components/alloq-offer/src/alloq_offer/workshop/export/docx_renderer.py
  - components/alloq-offer/src/alloq_offer/workshop/content/schema.py
  - scripts/inventory_docx.py
  - scripts/build_quo_layout.py
---

# Offer workshop template (QUO)

The workshop fills the customer template `Templates/QUO-33441-N7R0Z4_Preisindikation MVP Referenzdatenbank Treystar .docx`.
`scripts/inventory_docx.py` prints its structure; `scripts/build_quo_layout.py` turns it into the package layout.

## What is fixed and what is generated

| Part | Source in the QUO file | In the package |
| --- | --- | --- |
| Cover (title, customer, date, quote id) | paragraphs 0 to 25 | `layout.docx` with `{{ project_title }}`, `{{ customer_name }}`, `{{ customer_street }}`, `{{ customer_city }}`, `{{ customer_short }}`, `{{ offer_date }}`, `{{ quote_id }}` |
| Legal notice, supplier address | cover | fixed text |
| Table of contents | missing in the QUO file | TOC field `1-3`, updated when Word opens the file |
| Chapters Management Summary to Consumption | Heading 1 to 3 | removed from the layout, rendered from typed chapters at the anchor `[[KAPITEL]]` |
| Rechtliche Bestimmungen, Bindefrist (`{{ validity_date }}`), Sonstiges, Anlagen, Unterschriften | tail | fixed text; signature placeholders (`$$_PRT_..._$$`) stay untouched |

Customer data is removed from the layout. There is no story map chapter: the document shows written stories only.

## Chapters (`chapters.yaml`)

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
