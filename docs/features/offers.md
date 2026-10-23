---
title: Offers
description: How offer editors, project managers and admins list, create, edit, send and archive customer offers on the page "Angebote", and how an admin gives a user access to the offers only.
story_ids: [OFF-01, OFF-02, OFF-03, OFF-04, OFF-05, OFF-06, OFF-07, OFF-08, OFF-09]
source_paths:
  - components/alloq-offer/src/alloq_offer/entities.py
  - components/alloq-offer/src/alloq_offer/models.py
  - components/alloq-offer/src/alloq_offer/repository.py
  - components/alloq-offer/src/alloq_offer/services/offers.py
  - components/alloq-offer/src/alloq_offer/states/offer_state.py
  - components/alloq-offer/src/alloq_offer/components/offer_table.py
  - components/alloq-offer/src/alloq_offer/components/offer_inspector.py
  - components/alloq-offer/src/alloq_offer/components/offer_modal.py
  - components/alloq-offer/src/alloq_offer/components/offer_parts.py
  - components/alloq-offer/src/alloq_offer/components/offer_toolbar.py
  - components/alloq-offer/src/alloq_offer/pages.py
  - components/alloq-offer/src/alloq_offer/states/industry_state.py
  - components/alloq-offer/src/alloq_offer/components/industry.py
  - app/pages/industries.py
  - components/alloq-commons/src/alloq_commons/roles.py
  - components/alloq-commons/src/alloq_commons/access.py
  - app/components/sidebar.py
  - app/app.py
  - alembic/versions/2026_10_21_offers.py
  - alembic/versions/2026_10_21_industries.py
last_verified_commit: "63da7bd (unreleased offers package)"
---

# Offers

This page covers the page "Angebote" [offers] at `/offers`. It lists the offers that the company calculated for customer projects, with person days, risk buffer, production cost and recommended price. The stories belong to the activity "Prepare offers" on the [story map](./story-map.md).

The page has four user tasks:

- **Find an offer.** Read the list grouped by status, search, filter and sort it, and read one offer in the inspector.
- **Create an offer.** Enter a new offer in the form "Neues Angebot" [new offer].
- **Maintain an offer.** Edit an offer, change its status and sent date in the inspector, and archive or restore it.
- **Give access to offers.** An admin gives a user the role "Angebote" [offers].
- **Maintain the industries.** An admin keeps the list "Branchen" [industries] that the offer form offers.

An offer is one row in `OfferEntity` (table `offers`). All values are typed in by hand. Alloq does not calculate them from daily rates, and an offer is not linked to a project. Offers are never deleted. The package has no delete handler, and an offer that is no longer needed is archived.

Admins, project managers and users with the role `offer_editor` can open the page and change offers. In this page the persona "Offer editor" means all three. Every data handler has the guard `requires_offer_editor`. The code lives in the independent package `components/alloq-offer`, which imports only `alloq-commons` and appkit.

## OFF-01 Offer list grouped by status {#off-01}

Show all offers in one table, grouped by status, with sums in the footer.

As an offer editor, I want to see all open offers grouped by status, so that I know which offers are new, which are in progress and which are sent.

Offer editor · Find an offer / Read the list · priority 1 · core · unreleased

### Acceptance criteria

1. **Given** a user who may edit offers, **when** they open `/offers`, **then** `load_offers` loads all offers with the newest change first. The loader shows only on the first load, and later loads keep the list on screen.
2. **Given** the loaded offers, **when** the table renders, **then** it shows the columns "Angebot" [offer] with title and customer, "Account Manager", "Branche" [industry], "Status", "Personentage" [person days], "Kosten" [cost], "Preis" [price] and "Versendet am" [sent on].
3. **Given** active offers, **when** the table renders, **then** they appear in the groups "Neu" [new], "In Bearbeitung" [in progress] and "Versendet" [sent], in this order, and a group without offers is hidden. Each status has its own badge colour.
4. **Given** an offer, **when** its row renders, **then** "Personentage" shows person days plus risk buffer with the unit "PT", "Kosten" and "Preis" show euros with two decimals, and "Versendet am" shows the date as DD.MM.YYYY or "–" when there is none.
5. **Given** the visible offers, **when** the footer row "Summe" [sum] renders, **then** it shows the sums of person days (with buffer), cost and price of exactly the visible rows.
6. **Given** the offers, **when** the toolbar renders, **then** the subtitle says how many offers are not archived and how many of them are not yet sent, e.g. "4 Angebote · 3 offen" [4 offers, 3 open].
7. **Given** no offers at all, **when** the page renders, **then** it shows "Noch keine Angebote vorhanden." [no offers yet]. **Given** offers but none that match the filter, **then** it shows "Keine Angebote mit diesem Filter." [no offers with this filter].
8. **Given** a database error, **when** the offers load, **then** the toast "Die Angebote konnten nicht geladen werden." [offers could not be loaded] appears without the error text.

### Evidence

- [offer_state.py](../../components/alloq-offer/src/alloq_offer/states/offer_state.py): `OfferState.load_offers`, `OfferState.grouped`, `OfferState.new_rows`, `OfferState.in_progress_rows`, `OfferState.sent_rows`, `OfferState.total_person_days`, `OfferState.total_production_cost`, `OfferState.total_recommended_price`, `OfferState.subtitle`
- [offer_table.py](../../components/alloq-offer/src/alloq_offer/components/offer_table.py): `COLUMNS`, `GROUPS`, `_row`, `_group`, `_total_row`, `offer_table`
- [offer_parts.py](../../components/alloq-offer/src/alloq_offer/components/offer_parts.py): `STATE_TONES`, `state_badge`, `euro`, `days`, `date_or_dash`, `EMPTY_ALL`, `EMPTY_FILTERED`
- [offers.py](../../components/alloq-offer/src/alloq_offer/services/offers.py): `group_offers`, `totals`, `total_days`
- [repository.py](../../components/alloq-offer/src/alloq_offer/repository.py): `OfferRepository.find_all_ordered`
- [pages.py](../../components/alloq-offer/src/alloq_offer/pages.py): `create_offers_page`
- Tests: [test_offer_state.py](../../components/alloq-offer/tests/test_offer_state.py) `TestDataHandlers.test_load`, `TestDataHandlers.test_load_error`, `TestUiHandlers.test_groups_and_archived`; [test_offer_services.py](../../components/alloq-offer/tests/test_offer_services.py) `TestDerived.test_totals`, `TestDerived.test_totals_empty`, `TestSortAndGroup.test_group`; [test_offer_repository.py](../../components/alloq-offer/tests/test_offer_repository.py) `test_find_all_ordered_newest_first`; [test_offer_components.py](../../components/alloq-offer/tests/test_offer_components.py) `test_table_renders_groups_and_columns`, `test_table_empty_texts_are_constants`, `test_state_tones_cover_all_states`, `test_page_factory`

## OFF-02 Search, filter and sort offers {#off-02}

Narrow the list down by text, by status or to the archive, and sort it by a column.

As an offer editor, I want to search, filter and sort the offers, so that I find one offer quickly in a long list.

Offer editor · Find an offer / Narrow the list · priority 2 · comfort · unreleased

### Acceptance criteria

1. **Given** text in the search field "Angebot, Kunde oder Account Manager" [offer, customer or account manager], **when** the list filters, **then** it keeps the offers whose title, customer or key accounter contain the text, ignoring case and surrounding spaces.
2. **Given** the filter segments "Alle" [all], "Neu", "In Bearbeitung", "Versendet" and "Archiviert" [archived], **when** the user picks "Alle" or a status, **then** the list shows only active offers, all or of that status.
3. **Given** the segment "Archiviert", **when** the user picks it, **then** the list shows only archived offers, in one group "Archiviert". Archived offers never show under any other segment.
4. **Given** an unknown filter value, **when** `set_list_filter` gets it, **then** the filter falls back to "Alle".
5. **Given** a column header, **when** the user clicks it, **then** the list sorts by that column ascending, and a second click sorts it descending. Text sorts ignore case, "Status" sorts in the group order, and "PT" sorts by person days plus buffer.
6. **Given** a sort by "Versendet am", **when** the list sorts, **then** offers without a sent date come last in both directions.

### Evidence

- [offers.py](../../components/alloq-offer/src/alloq_offer/services/offers.py): `FILTERS`, `SORT_COLUMNS`, `search_offers`, `filter_offers`, `sort_offers`, `visible_offers`
- [offer_state.py](../../components/alloq-offer/src/alloq_offer/states/offer_state.py): `OfferState.set_search_filter`, `OfferState.set_list_filter`, `OfferState.toggle_sort`, `OfferState.visible`, `OfferState.archived_rows`
- [offer_toolbar.py](../../components/alloq-offer/src/alloq_offer/components/offer_toolbar.py): `SEARCH_PLACEHOLDER`, `offer_filter`, `offer_toolbar`
- [offer_table.py](../../components/alloq-offer/src/alloq_offer/components/offer_table.py): `offer_list`
- Tests: [test_offer_services.py](../../components/alloq-offer/tests/test_offer_services.py) `TestSearchAndFilter.test_search`, `TestSearchAndFilter.test_filter_all_hides_archived`, `TestSearchAndFilter.test_filter_state`, `TestSearchAndFilter.test_filter_archived`, `TestSortAndGroup.test_sort_title_case_insensitive`, `TestSortAndGroup.test_sort_numbers_use_total_days`, `TestSortAndGroup.test_sort_state_follows_group_order`, `TestSortAndGroup.test_sent_date_puts_empty_last`, `TestSortAndGroup.test_unknown_column_keeps_order`, `TestSortAndGroup.test_visible_offers_combines_all`; [test_offer_state.py](../../components/alloq-offer/tests/test_offer_state.py) `TestUiHandlers.test_filter_and_sort`; [test_offer_components.py](../../components/alloq-offer/tests/test_offer_components.py) `test_toolbar`

## OFF-03 Offer inspector {#off-03}

Read the key data and the calculation of one offer in the panel on the right.

As an offer editor, I want to see the details and the margin of the selected offer next to the list, so that I can check an offer without opening a form.

Offer editor · Find an offer / Read one offer · priority 3 · core · unreleased

### Acceptance criteria

1. **Given** no selected row, **when** the inspector "Angebotsdetails" [offer details] renders, **then** it shows "Kein Angebot ausgewählt." [no offer selected].
2. **Given** a click on a row, **when** the inspector renders, **then** it shows title, customer and status badge of that offer, and the tag "Archiviert" when it is archived. If a filter hides the selected offer, the inspector shows nothing selected again.
3. **Given** a selected offer, **when** the section "Eckdaten" [key data] renders, **then** it shows "Status", "Versendet am", "Branche" [industry] with the name of the industry, "Account Manager" and "Dokumente" [documents].
4. **Given** a document link, **when** the inspector renders, **then** "Öffnen" [open] opens it in a new tab and a copy icon copies it with the toast "Link kopiert" [link copied]. Without a link it shows "–". (no test)
5. **Given** a selected offer, **when** the section "Kalkulation" [calculation] renders, **then** it shows "Personentage" [person days], "Risikopuffer" [risk buffer], "Gesamtaufwand" [total effort] as person days plus buffer, "Kosten" [cost], "Empfohlener Preis" [recommended price] and "Marge" [margin].
6. **Given** a recommended price above 0, **when** the margin shows, **then** it is (VK − HK) / VK × 100 with one decimal and a German comma, e.g. "50,0 %". **Given** a price of 0, **then** it shows "–".
7. **Given** the icon "Inspektor ein- oder ausblenden" [show or hide inspector], **when** the user clicks it, **then** the inspector hides or shows, and the browser remembers the choice in `alloq_offers_inspector`.

### Evidence

- [offer_inspector.py](../../components/alloq-offer/src/alloq_offer/components/offer_inspector.py): `offer_inspector`, `_heading`, `_details`, `_sharepoint`, `_copy_icon`
- [offer_state.py](../../components/alloq-offer/src/alloq_offer/states/offer_state.py): `OfferState.inspect`, `OfferState.inspected`, `OfferState._named`, `OfferState.inspected_total_days`, `OfferState.inspected_margin`, `OfferState.toggle_inspector`, `OfferState.show_inspector`
- [offers.py](../../components/alloq-offer/src/alloq_offer/services/offers.py): `total_days`, `margin_pct`
- Tests: [test_offer_state.py](../../components/alloq-offer/tests/test_offer_state.py) `TestUiHandlers.test_inspector`, `TestUiHandlers.test_nothing_inspected_without_selection`; [test_offer_services.py](../../components/alloq-offer/tests/test_offer_services.py) `TestDerived.test_total_days`, `TestDerived.test_margin`, `TestDerived.test_margin_none_without_price`; [test_offer_components.py](../../components/alloq-offer/tests/test_offer_components.py) `test_inspector_renders`

## OFF-04 Create an offer {#off-04}

Enter a new offer with its numbers, customer data and status.

As an offer editor, I want to enter a new offer with person days, buffer, cost and price, so that the team keeps all offers in one place.

Offer editor · Create an offer / Enter the offer · priority 1 · core · unreleased

### Acceptance criteria

1. **Given** the button "Angebot anlegen" [create offer], **when** the user clicks it, **then** the empty dialog "Neues Angebot" [new offer] opens with "Risikopuffer (Personentage)" set to 0 and "Status" set to "Neu". Reopening the dialog clears the inputs again.
2. **Given** the dialog, **when** it renders, **then** it has the fields "Angebotstitel" [offer title], "Kunde" [customer], "Account Manager", "Branche" [industry], "Kalkulierte Personentage" [calculated person days], "Risikopuffer (Personentage)", "Kosten" [cost], "Empfohlener Preis" [recommended price], "Status", "Versendet am" and "Link zu den Dokumenten" [link to the documents]. "Branche" lists the industries from [OFF-09](#off-09) by name.
3. **Given** an empty title, customer, account manager or industry, **when** the dialog renders, **then** the button "Angebot speichern" [save offer] is disabled.
3a. **Given** empty calculation fields (person days, buffer, cost, price), **when** the user saves, **then** they are stored as 0, because the calculation exists only after the offer workshop. Lists and the inspector show "–" for 0.
4. **Given** the number fields, **when** the user types, **then** they accept no negative values and at most two decimals, with a German comma. A value such as "1.120 €" is read as 1120.
5. **Given** the text fields, **when** the user types, **then** the browser stops at 255 characters, and at 2048 for the document link.
6. **Given** text with only spaces, a negative number, no industry, an unknown status, or a document link that does not start with `http://` or `https://`, **when** the user saves, **then** `OfferCreate` rejects it, the toast "Bitte alle Pflichtfelder ausfüllen. Zahlen dürfen nicht negativ sein, ein Link muss mit https:// beginnen." [fill in all required fields] appears and nothing is stored. An empty link is stored as no link.
7. **Given** the status "Versendet" and no sent date, **when** the user saves, **then** the sent date becomes today.
8. **Given** valid input, **when** the user saves, **then** the offer is stored, appears in the list and is selected in the inspector, the dialog closes and the toast "Angebot '…' angelegt." [offer created] appears, with the title of the offer in place of the dots.
9. **Given** a database error, **when** the user saves, **then** the toast "Das Angebot konnte nicht gespeichert werden." [offer could not be saved] appears without the error text.

### Evidence

- [offer_modal.py](../../components/alloq-offer/src/alloq_offer/components/offer_modal.py): `TITLE_CREATE`, `_text`, `_number`, `offer_form_fields`, `_form`, `offer_modal`
- [offer_toolbar.py](../../components/alloq-offer/src/alloq_offer/components/offer_toolbar.py): `offer_toolbar`
- [offer_state.py](../../components/alloq-offer/src/alloq_offer/states/offer_state.py): `REQUIRED_FIELDS`, `HINT_INVALID`, `ERROR_SAVE`, `_empty_form`, `number_text`, `OfferState.open_create_modal`, `OfferState.set_form_field`, `OfferState.is_form_invalid`, `OfferState.create_offer`, `OfferState._save_form`, `OfferState._data_from`
- [models.py](../../components/alloq-offer/src/alloq_offer/models.py): `OfferCreate`, `OfferCreate._check_url`
- [offers.py](../../components/alloq-offer/src/alloq_offer/services/offers.py): `apply_state_change`
- [entities.py](../../components/alloq-offer/src/alloq_offer/entities.py): `OfferEntity`, `OfferStateEnum`
- [2026_10_21_offers.py](../../alembic/versions/2026_10_21_offers.py): table `offers`
- Tests: [test_offer_state.py](../../components/alloq-offer/tests/test_offer_state.py) `TestNumberText.test_normalizes`, `TestUiHandlers.test_modal_and_form`, `TestDataHandlers.test_create`, `TestDataHandlers.test_create_sent_sets_today`, `TestDataHandlers.test_create_invalid`, `TestDataHandlers.test_create_error`; [test_offer_model.py](../../components/alloq-offer/tests/test_offer_model.py) `TestOfferCreate.test_valid_defaults`, `TestOfferCreate.test_strips_text`, `TestOfferCreate.test_rejects_empty_text`, `TestOfferCreate.test_rejects_negative_numbers`, `TestOfferCreate.test_rejects_missing_industry_and_unknown_state`, `TestOfferCreate.test_sharepoint_url_rules`, `TestOfferEntity.test_to_dict_has_all_keys`; [test_offer_components.py](../../components/alloq-offer/tests/test_offer_components.py) `test_modal_has_all_fields`

### Open questions

- The browser limit of 255 characters comes from `custom_attrs={"maxLength": ...}`, and the server limit from `OfferCreate`. No test checks the browser limit.

## OFF-05 Edit an offer {#off-05}

Change any value of an existing offer in the same form.

As an offer editor, I want to change an offer after I entered it, so that the numbers stay correct when the calculation changes.

Offer editor · Maintain an offer / Edit the offer · priority 1 · core · unreleased

### Acceptance criteria

1. **Given** a double click on a row or the button "Bearbeiten" [edit] in the inspector, **when** the dialog opens, **then** its title is "Angebot bearbeiten" [edit offer], it holds the stored values of the offer, and the offer is selected in the inspector.
2. **Given** changed values, **when** the user saves, **then** the same checks as in [OFF-04](#off-04) apply, the stored offer is updated, the dialog closes and the toast "Angebot '…' aktualisiert." [offer updated] appears, with the title in place of the dots.
3. **Given** the status "Versendet" and no sent date, **when** the user saves, **then** the sent date becomes today, as in [OFF-04](#off-04).
4. **Given** an offer that no longer exists, or a save without an offer to edit, **when** the user saves, **then** the toast "Angebot nicht gefunden." [offer not found] appears and no new offer is created.

### Evidence

- [offer_state.py](../../components/alloq-offer/src/alloq_offer/states/offer_state.py): `_form_from`, `OfferState.open_edit_modal`, `OfferState.update_offer`, `OfferState._save_form`, `NOT_FOUND`
- [offer_modal.py](../../components/alloq-offer/src/alloq_offer/components/offer_modal.py): `TITLE_EDIT`, `offer_modal`
- [offer_table.py](../../components/alloq-offer/src/alloq_offer/components/offer_table.py): `_row`
- [offer_inspector.py](../../components/alloq-offer/src/alloq_offer/components/offer_inspector.py): `_actions`
- Tests: [test_offer_state.py](../../components/alloq-offer/tests/test_offer_state.py) `TestUiHandlers.test_modal_and_form`, `TestDataHandlers.test_update`, `TestDataHandlers.test_update_missing`, `TestUpdateWithoutEditId.test_update_without_editing_id_does_not_create`

## OFF-06 Change status and sent date in the inspector {#off-06}

Move an offer to the next status and set its sent date without opening the form.

As an offer editor, I want to mark an offer as sent in the inspector, so that the sent date is recorded on the day I send it.

Offer editor · Maintain an offer / Track the status · priority 2 · core · unreleased

### Acceptance criteria

1. **Given** the status select in the inspector, **when** the user picks "Versendet" and the stored offer has no sent date, **then** the status and today's date are saved and the toast "Status gespeichert." [status saved] appears.
2. **Given** a stored sent date, **when** the user picks any status, also an earlier one, **then** the date stays as it is.
3. **Given** the status change, **when** it is saved, **then** the decision uses the offer as stored in the database, not the list in the browser, so a stale list cannot overwrite a newer date.
4. **Given** a status that is not "Neu", "In Bearbeitung" or "Versendet", **when** it reaches the handler, **then** the toast "Ungültiger Status." [invalid status] appears and nothing is stored.
5. **Given** the date input "Versendet am", **when** the user picks or types a date, **then** it is saved when the field loses focus, with the toast "Datum gespeichert." [date saved]. An unchanged date stores nothing.
6. **Given** the icon "Heute" [today] in the date input, **when** the user clicks it, **then** today's date is put into the field and saved.
7. **Given** a date that cannot be read, **when** the field loses focus, **then** the toast "Bitte ein gültiges Datum eingeben." [enter a valid date] appears and nothing is stored.
8. **Given** a user who may not edit offers, **when** the inspector renders, **then** the status select and the date input are disabled. (no test)

### Evidence

- [offer_state.py](../../components/alloq-offer/src/alloq_offer/states/offer_state.py): `OfferState.update_inspected_state`, `OfferState.set_inspected_sent_date`, `OfferState.set_sent_date_today`, `OfferState.save_inspected_sent_date`, `OfferState.inspected_sent_date`, `OfferState._persist`
- [offers.py](../../components/alloq-offer/src/alloq_offer/services/offers.py): `apply_state_change`
- [offer_inspector.py](../../components/alloq-offer/src/alloq_offer/components/offer_inspector.py): `STATE_OPTIONS`, `_sent_date_input`, `_details`
- Tests: [test_offer_services.py](../../components/alloq-offer/tests/test_offer_services.py) `TestApplyStateChange.test_sets_today_when_sent_without_date`, `TestApplyStateChange.test_keeps_existing_date_when_sent`, `TestApplyStateChange.test_keeps_date_when_moving_back`, `TestApplyStateChange.test_no_date_for_other_states`; [test_offer_state.py](../../components/alloq-offer/tests/test_offer_state.py) `TestDataHandlers.test_state_change_sets_date`, `TestDataHandlers.test_state_change_keeps_date`, `TestDataHandlers.test_state_change_invalid`, `TestDataHandlers.test_sent_date_edit`, `TestDataHandlers.test_sent_date_edge_cases`, `TestUiHandlers.test_sent_date_draft`, `TestUiHandlers.test_sent_date_today_sets_draft`

### Open questions

- "Today" is the UTC date (`_today`). Shortly after midnight German time, the UTC date is still the day before. The same question is open for absences in [TEAM-12](./absences.md#team-12).
- The date input in the inspector cannot be cleared. A sent date can only be removed in the dialog "Angebot bearbeiten".

## OFF-07 Archive and restore an offer {#off-07}

Take an offer out of the list without deleting it, and bring it back.

As an offer editor, I want to archive an offer that is no longer relevant, so that the list shows only current offers and old ones are still there.

Offer editor · Maintain an offer / Archive the offer · priority 3 · core · unreleased

### Acceptance criteria

1. **Given** an active offer in the inspector, **when** the user clicks "Archivieren" [archive], **then** the offer is marked archived, leaves the active list and the toast "Angebot archiviert." [offer archived] appears.
2. **Given** an archived offer under the filter "Archiviert", **when** the user clicks "Wiederherstellen" [restore], **then** it is active again and the toast "Angebot wiederhergestellt." [offer restored] appears.
3. **Given** any offer, **when** a user looks for a way to delete it, **then** there is none. Offers are only archived.
4. **Given** an offer that no longer exists, **when** the user archives or restores it, **then** the toast "Angebot nicht gefunden." appears. **Given** a database error, **then** the toast "Das Angebot konnte nicht gespeichert werden." appears.

### Evidence

- [offer_state.py](../../components/alloq-offer/src/alloq_offer/states/offer_state.py): `OfferState.archive_offer`, `OfferState.restore_offer`, `OfferState._persist`
- [offer_inspector.py](../../components/alloq-offer/src/alloq_offer/components/offer_inspector.py): `_actions`
- [entities.py](../../components/alloq-offer/src/alloq_offer/entities.py): `OfferEntity.archived`
- Tests: [test_offer_state.py](../../components/alloq-offer/tests/test_offer_state.py) `TestDataHandlers.test_archive_and_restore`, `TestDataHandlers.test_persist_error`

## OFF-08 Give a user access to the offers only {#off-08}

Let a person work on offers without seeing the planning, the projects or the team.

As an administrator, I want to give a user the role "Angebote", so that sales people can maintain offers without access to the capacity planning.

Administrator · Give access to offers / Assign the role · priority 1 · core · unreleased

### Acceptance criteria

1. **Given** the user management, **when** an admin edits a user, **then** the role "Angebote" (`offer_editor`, id 3, "Lesen und Bearbeiten der Angebote" [read and edit offers]) is offered next to the other roles.
2. **Given** an admin, a project manager or a user with the role `offer_editor`, **when** they call any offer data handler, **then** it runs. Employees and users without these roles get an error, and users who are not signed in are sent to the sign-in page.
3. **Given** a user with only the role `offer_editor`, **when** the access rules are checked, **then** they may not read or edit the planning, the projects or the team.
4. **Given** a user with only the role `offer_editor`, **when** the sidebar renders, **then** the section "Planung" [planning] shows only "Angebote". (no test)
5. **Given** a user who may edit offers but not read the planning, **when** they open another page, **then** the no-access message shows the link "Zu den Angeboten" [to the offers]. (no test)
6. **Given** a user who may not edit offers, **when** they open `/offers`, **then** they see the no-access message instead of the list.
7. **Given** a new handler in `alloq_offer`, **when** the guard test runs, **then** it fails unless the handler has `requires_offer_editor` or is listed as UI only. Offer handlers must not use `requires_admin` or `requires_editor`.

### Evidence

- [roles.py](../../components/alloq-commons/src/alloq_commons/roles.py): `OFFER_EDITOR_ROLE`, `ALL_ROLES`
- [access.py](../../components/alloq-commons/src/alloq_commons/access.py): `CAN_EDIT_OFFERS`, `can_edit_offers`, `offers_only`, `requires_offer_editor`, `no_access`
- [sidebar.py](../../app/components/sidebar.py): `OFFERS_ROUTE`, `PLANNING_ITEMS`, `ROUTE_GUARDS`, `_guarded_nav_item`, `sidebar`
- [pages.py](../../components/alloq-offer/src/alloq_offer/pages.py): `create_offers_page`
- [app.py](../../app/app.py): `create_offers_page`
- Tests: [test_access.py](../../components/alloq-commons/tests/test_access.py) `TestOfferEditor.test_role_is_offered_in_user_management`, `TestOfferEditor.test_can_edit_offers`, `TestOfferEditor.test_offer_editor_gets_no_planning_access`, `TestOfferEditor.test_frontend_var_and_guard_component`, `TestOfferEditor.test_allowed_users_run_the_handler`, `TestOfferEditor.test_others_are_denied`, `TestOfferEditor.test_anonymous_users_are_redirected`; [test_handler_authorization.py](../../tests/test_handler_authorization.py) `test_offer_handlers_use_the_offer_editor_level`, `test_offer_handlers_are_not_admin_or_editor_guarded`

## OFF-09 Maintain the industries {#off-09}

Keep the list of customer industries that an offer can belong to.

As an administrator, I want to add, rename and delete industries, so that the offer form uses words that fit our customers.

Administrator · Maintain the industries / Edit the list · priority 2 · core · unreleased

### Acceptance criteria

1. **Given** a signed-in admin, **when** the admin opens `/admin/industries` ("Branchen" [industries] in the section "Administration"), **then** the table lists all industries ordered by name. The loading row "Lade Branchen..." [loading industries] only shows on the first load.
2. **Given** the migration `f1a2b3c4d5e6`, **when** it runs, **then** it creates one industry per former CIU code ("Verbraucherdienstleistungen", "Finanzdienstleistungen", "Energie und Versorgung", "Öffentlicher Sektor", "Gesundheitswesen", "Industrie und Mittelstand"), links every offer to its industry and drops the column `ciu`. An unknown code becomes an industry with the code as its name. The downgrade restores the codes.
3. **Given** a name, **when** the admin saves "Neue Branche" [new industry] or renames an industry, **then** the name is stored without surrounding spaces. An empty name or one longer than 100 characters shows "Bitte einen Namen mit höchstens 100 Zeichen angeben." [enter a name of at most 100 characters], and a name that exists shows "Diese Branche gibt es bereits." [this industry exists].
4. **Given** a renamed industry, **when** the offers load again, **then** the offers show the new name.
5. **Given** an industry that offers use, archived ones included, **when** the admin deletes it, **then** it stays and the toast says in how many offers it is used. The database also refuses the delete (`ON DELETE RESTRICT`).
6. **Given** text in "Branchen suchen" [search industries], **when** the table renders, **then** it shows only the industries whose name contains the text, ignoring case.
7. **Given** a user who is not an admin, **when** they call a data handler of `IndustryState`, **then** it does not run. The handlers use `requires_admin` like the other administration pages, although the state lives in `alloq_offer`.

### Evidence

- [entities.py](../../components/alloq-offer/src/alloq_offer/entities.py): `IndustryEntity`, `OfferEntity.industry_id`
- [models.py](../../components/alloq-offer/src/alloq_offer/models.py): `Industry`, `IndustryCreate`, `Offer.industry`
- [repository.py](../../components/alloq-offer/src/alloq_offer/repository.py): `IndustryRepository.find_all_ordered`, `IndustryRepository.count_offers`
- [industry_state.py](../../components/alloq-offer/src/alloq_offer/states/industry_state.py): `IndustryState`, `in_use_message`, `load_industries`
- [industry.py](../../components/alloq-offer/src/alloq_offer/components/industry.py): `industries_table`, `industries_toolbar`, `industry_form_fields`
- [industries.py](../../app/pages/industries.py): `create_industries_page`
- [sidebar.py](../../app/components/sidebar.py): `ADMIN_ITEMS`
- [2026_10_21_industries.py](../../alembic/versions/2026_10_21_industries.py): table `industries`, column `offers.industry_id`
- Tests: [test_industry_state.py](../../components/alloq-offer/tests/test_industry_state.py); [test_offer_repository.py](../../components/alloq-offer/tests/test_offer_repository.py) `test_industries_are_ordered_by_name`, `test_count_offers_includes_archived`; [test_migrations.py](../../tests/test_migrations.py) `test_industries_migration_links_offers_and_restores_codes`; [test_handler_authorization.py](../../tests/test_handler_authorization.py) `ADMIN_STATES`
