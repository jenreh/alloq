---
name: german-ui-copy
description: Alloq UI text conventions (German labels, tone, number and date formats, terminology). Use when writing or changing user-visible strings in Alloq pages, dialogs, tables, tooltips, notifications or empty states.
user-invocable: false
---

# German UI copy

- User-visible text is German; code, comments and logs are English.
- Address the user formally and briefly: "Angebot speichern", not "Du kannst ...".
- Buttons use verb + noun ("Projekt anlegen", "Abbrechen"); destructive confirmations
  name the object ("Angebot wirklich löschen?").
- Use real umlauts (ä ö ü ß), never ae/oe/ue.
- Numbers: `1.120,50 €` (dot thousands, comma decimals, space before €); dates `TT.MM.JJJJ`.
- Empty states say what is missing and what to do next.
- Keep terms consistent with existing screens: search the repo for the German word
  before inventing a new one (`grep -rn "Angebot" components/ app/`).
- Put strings used by both UI and tests in module constants.
