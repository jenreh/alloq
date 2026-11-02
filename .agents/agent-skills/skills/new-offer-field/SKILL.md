---
name: new-offer-field
description: Checklist for adding a field to the Alloq offer feature across entity, model, repository, service, state, component, migration and tests. Use when the user asks to add or change a column or attribute on offers.
disable-model-invocation: true
---

# New offer field

Load `alloq-implementation` first. Package: `components/alloq-offer/src/alloq_offer/`.
Write the failing test first, then work through the layers in this order:

1. `entities.py` - add the column and include it in `to_dict()`.
2. `models.py` - read model field and the create/update model with `Field` limits.
3. `repository.py` - include the field in create/update paths and any eager loading.
4. `services/offers.py` - validation or calculation if the field affects totals.
5. `states/offer_state.py` - var, setter handler, load into the edit form. Follow the
   handler authorization contract (offers: edit needs `offer_editor`; see `handler-auth-audit`).
6. `components/offer_modal.py` and `offer_inspector.py` - input and display. German
   labels (see `german-ui-copy`). Use `custom_attrs={"maxLength": N}` for text limits.
   Wrap `de_number` in `mn.text` for text props.
7. `alembic/versions/YYYY_MM_DD_<topic>.py` - hand-written, `batch_alter_table`,
   real `downgrade()`. Run the `migration-check` skill. Never run the migration yourself.
8. Tests in `components/alloq-offer/tests/`: model, repository, services, state, components,
   plus `tests/test_migrations.py` if the chain changed.
9. Gates: `task format && task lint && task typecheck`, then
   `uv run pytest components/alloq-offer/tests -q`.
