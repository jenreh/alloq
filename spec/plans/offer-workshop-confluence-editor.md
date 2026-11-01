# Offer workshop: Confluence-style chapter editing and sub chapters

## Task
Make chapter editing in the offer workshop (Kapitel tab) behave like Confluence:
one continuous page, one fixed formatting toolbar, full text formatting in text chapters.
Tables and images stay their own chapter types. The chapter navigation on the left
stays, and gets real sub chapters (today every row looks like the same level).

Decisions already made with the user:
- Continuous document (several chapters editable in one flow), not one-chapter-at-a-time.
- One fixed toolbar (Confluence), no second bubble/selection menu.
- Text chapters: all text options, but no image and no table inside text.
- Table and image are chapter types (`table` exists, `image` is new).
- The outline (left column) stays; the right chapter panel stays.
- Table and image chapters are automatically sub chapters (level 2) and have no
  headline. They carry an optional description (shown as caption). They are not numbered
  and always sit under the text chapter before them. Stories and calc chapters keep their
  headline and level choice.

## Findings (current state)
- Editor: `components/chapters/chapter_editor.jsx` (Tiptap 3.32 via `@mantine/tiptap`,
  StarterKit with only bold, italic, h3/h4, lists, undo/redo). Python wrapper
  `components/chapters/editor.py`. Only the selected block mounts an editor; the others
  are read-only HTML (`blocks/prose.py`, `document.py::_block`). Selecting is a server
  round trip (`ChapterState.select_chapter` -> `_load_active`), so clicking into text
  feels slow and the border box jumps (`.aq-doc-block[data-selected]` in
  `assets/css/aq-workshop.css`).
- The formatting toolbar floats per block (`.aq-doc-float`), AI menu "KI" sits inside it.
- Content model `content/schema.py`: `Run` has only `bold`/`italic`; prose blocks are
  paragraph, heading 3/4, bullet list, ordered list, plus `TableBlock`/`BoundValue`.
  `content/editor_io.py` rejects everything else (`UNSUPPORTED_NAMES`) and
  `editor_compatible` falls back to read-only for tables/bound values.
  Consumers of the model: `export/chapter_renderers.py` (python-docx `Writer`),
  `content/text.py`, `ai/render.py`, `services/chapter_blocks.py`.
- `autosave(key, html)` in `states/chapter_state.py` already saves for any `key`, not only
  the active chapter. Revisions, locks (`chapter_locked`) and proposals are per chapter.
- Sub chapters: data already has `level` 1/2 (`ChapterEntity.level`,
  `services/outline.py::set_level`, `LEVELS = (1, 2)`, numbers from
  `services/numbering.outline_numbers`). Weak spots: level is only set with a segmented
  control in the right panel (`panel.py::_settings`), the outline row just gets 22px
  padding (`.aq-doc-row[data-level="2"]`), a blank chapter copies the level of the one
  before it, dragging moves one row without its children, no way to add a sub chapter
  from the navigation.

## Requirements

### A. Navigation with sub chapters (ship first, independent of the editor)
1. Each outline row (`components/chapters/outline.py::_row`) gets hover actions:
   "+ Unterkapitel" (adds a blank level-2 chapter directly after the row's last child) and
   indent/outdent buttons. Keyboard: Tab / Shift+Tab on the focused row.
2. Clear tree look: level-1 rows bold with their number, level-2 rows indented with a
   guide line, collapse/expand chevron on level-1 rows that have children (collapse state is
   per viewer, kept in the browser, not stored).
3. Dragging a level-1 chapter moves its sub chapters with it; a sub chapter can be dropped
   under another parent (its level follows the target). Extend `OutlineService.move_chapter`
   to move the group; keep `_renumber` rule that position 0 is level 1.
4. New service methods in `services/outline.py`: `add_subchapter(parent_key, ...)`,
   `indent(key)`, `outdent(key)`; handlers in `states/outline_mixin.py` next to
   `set_active_level` (same `@requires_offer_editor`, same `_outline_change` pattern).
   Keep the segmented "Ebene" control in the panel working.
5. "+ Kapitel einfügen" dialog (`dialogs.py`): a level choice (Kapitel / Unterkapitel);
   default level follows the selection.
6. Headline-less sub chapters for table and image (rule lives in the service, not only
   the UI): `OutlineService` forces `level = 2` for these types on add, move, indent and
   outdent (outdent/level 1 is refused with a German message; position 0 is refused too,
   they need a parent). Their numbering is skipped: extend
   `services/numbering.outline_numbers` so they get no number and do not advance the
   counter of their siblings. Deleting or moving a parent keeps the group together
   (requirement 3). Title field: stored but optional for these types (relax `_title` /
   `TITLE_NEEDED` for them); the outline row shows the description or the type label
   ("Tabelle", "Bild") instead of "number title", with a smaller, muted style.
7. Existing table chapters from templates/library blocks that have a title: keep the
   title in the data, stop showing it in the document and Word export (no heading), and
   keep it as the outline fallback label. Check `services/chapter_blocks.py` and the
   library block definitions (`_block_definition`) so a library table block also lands at
   level 2 with its description pre-filled from the old title.
8. Keep two levels. Reason: text headings use Heading 3/4 in the Word template; a third
   chapter level would collide. Confirm in `export/template_package.py` before deciding.

### B. Content model: all text options
1. Extend `Run` in `content/schema.py` (backward compatible defaults): `underline`,
   `strike`, `code`, `link` (href, http/https/mailto only), `sub`, `sup`, `highlight`,
   `color` (from a fixed palette of theme colors, not free hex).
2. New prose blocks: `Quote`, `CodeBlock`, `Rule`, `TaskList`; lists get nesting
   (`items` become item objects with `children`) and `Paragraph`/`Heading` get `align`.
   Existing stored JSON must still validate (migrate on read in `parse_content`, no DB
   migration needed because chapter content is JSON; if a type check constraint exists,
   hand-write an Alembic revision, never autogenerate, never run it).
3. `content/editor_io.py`: accept the new tags/attributes, still reject images and tables
   inside text with the German message ("Bilder" / "Tabellen" are chapter types), still
   report instead of dropping. Replace the single `_list` slot by a stack so nested lists
   parse. Keep the empty-paragraph filter. `editor_compatible` and `content_to_html` updated.
4. Consumers: `export/chapter_renderers.py` (underline/strike/code/sup/sub, hyperlinks,
   quote, code, rule, nested lists, alignment, task list as bullet with box character),
   `content/text.py` (plain text lines), `ai/render.py`, `services/chapter_blocks.py`.
   If the Word template lacks a style (e.g. "Quote"), fall back to the paragraph style with
   direct formatting rather than raising `RenderError`.
5. AI draft schemas (`ai/schemas.py`) keep producing the simple blocks; no change needed
   beyond validation still passing.

### C. Editor: continuous page with one fixed toolbar
1. `chapter_editor.jsx`: mount an editor for every prose chapter that is
   `editor_compatible`, lazily (render the stored HTML until the block is near the viewport,
   IntersectionObserver), so long offers stay fast.
2. Extensions: Underline, Strike, Code, CodeBlock, Blockquote, HorizontalRule, Link,
   Highlight, Color/TextStyle, Subscript, Superscript, TextAlign, TaskList/TaskItem,
   Placeholder, nested lists (ListKeymap, Tab/Shift+Tab). Heading levels stay 3 and 4.
   Markdown shortcuts come with the extensions. No Image, no Table extension.
   Add dependencies through the existing `lib_dependencies` list in `editor.py`
   (`TIPTAP_VERSION` pin from `appkit_mantine.tiptap`).
3. One toolbar, sticky at the top of the document column, built once (new
   `ChapterToolbar` component or the first block's). A small module-level store in the JSX
   tracks the focused editor; the toolbar subscribes and acts on it, disabled while no text
   chapter is focused or the chapter is protected. Groups: undo/redo | block style
   dropdown (Absatz, Überschrift, Kleine Überschrift, Zitat, Code) | bold, italic,
   underline, strike, code | color/highlight | lists (bullet, numbered, task, indent,
   outdent) | align | link | rule | KI menu (existing `_ai_tools`) . German labels extend
   `EDITOR_LABELS`.
4. Selection follows focus: editor `onFocus` calls `ChapterState.select_chapter(key)`
   (right panel, history, proposals keep working). Remove the per-block `editor_nonce`
   remount for prose; keep the existing "sync outside changes only when not focused"
   effect, key the editor by chapter key. Remount only for revision changes that come
   from restore/accept (compare `_editor_for`).
5. Per-chapter editability: add `editable` to each row of `ChapterState.chapters`
   (from `load_document`) so non-selected blocks know whether they can be edited.
6. Look: remove the bordered box per block; show the chapter title as the document heading
   (inline editable, saves through `rename_active`), a thin hover/focus marker at the left
   instead of the 2px border, type badge only on hover, Arrow Up/Down at the start/end of
   a text chapter moves the cursor into the neighbouring text chapter. Page typography
   unchanged (`.aq-doc-prose`). All CSS in `assets/css/aq-workshop.css` (no Python style
   strings), colors from `alloq_commons.theme`.
7. Autosave: keep debounce + blur save per key (`autosave`), one revision per change as
   today; stale editors never overwrite (existing conflict handling).

### C2. Notion-style block gutter inside text chapters (from the user's screenshot)
1. On hover over any text block (paragraph, heading, list item) a gutter appears in the
   left margin with "+" and a six-dot grip, as in the screenshot. Use
   `@tiptap/extension-drag-handle-react` (add to `lib_dependencies`, pinned to
   `TIPTAP_VERSION`, check it exists for 3.32 with Context7).
2. Grip: drag to move the block (lists move as a whole, an item moves inside its list);
   click opens a small menu: Duplizieren, Löschen, In ... umwandeln (Absatz, Überschrift,
   Kleine Überschrift, Aufzählung, Nummerierung, Aufgabe, Zitat, Code).
3. "+": inserts an empty paragraph below and opens the same block-type picker at it
   (insert-only, formatting still lives in the one fixed toolbar). The gutter is keyboard
   reachable through the toolbar and the menu; Escape closes.
4. Look as in the screenshot: nested bullets alternate disc, circle, square; inline code
   as a tinted chip with the theme's negative/red text; gutter icons muted, 20px targets,
   shown on hover and on focus within the block. CSS in `assets/css/aq-workshop.css`
   under `.aq-doc-prose`.
5. This gutter is block-level; the chapter-level "+" between two chapters (F) is a
   separate line-style control in the gap between blocks, so the two never overlap.

### D. Image chapter type
1. New `ImageContent` in `content/schema.py`: `chapter_type="image"`, blob reference,
   `alt`, `description` (optional, the visible caption), `width` (percent), `align`. Add the
   same optional `description: Inline` to `TableContent` (default empty, old JSON valid). Register in `ChapterContent`, `labels.py`
   (`TYPE_LABELS`, `TYPE_OPTIONS`, `TYPE_SHORT`, `TYPE_HINTS`), `blocks/image.py`
   (view + editing, mirroring `blocks/table.py`), `document.py::BLOCKS`.
2. Upload with `rx.upload` like `components/sources_panel.py` /
   `states/sources_state.py::handle_upload`; store bytes via `workshop/storage.py`
   (pass `get_asyncdb_session` to the blob store as noted in memory). PNG/JPEG only, size
   cap, content sniffing, no SVG.
3. Serve the image to the browser through an authorized route in `workshop/routes.py`
   (offer access check), not a public URL.
4. Word export: `Writer.image` using `python-docx` `add_picture` with width cap; the
   description follows as a caption paragraph (no Heading paragraph for image or table
   chapters; update `export/chapter_renderers.py` and the anchor/heading logic in
   `docx_renderer.py`); text/AI views get a plain line ("Bild: <alt>").
5. In the document these blocks render without the `<h2>` header (`document.py::_header`
   is skipped for table/image), just the content and the description as an inline editable
   caption below it. "+ Kapitel einfügen" offers "Tabelle" and "Bild" as "Einfügen unter
   dem Kapitel" (no title input, only an optional description); the right panel hides the
   Überschrift and Ebene controls for these types.
6. Add the type to "+ Kapitel einfügen" blank types. Handler authorization via
   `requires_offer_editor` as for the other chapter handlers.

### G. Stories chapter: filter by column (activity) and slice
Today a stories chapter takes all live stories of the map and only chooses the grouping
(`StoriesContent.group_by`, `blocks/stories.py`, panel `GROUP_BY`). An older `scopes`
setting was dropped. Bring back a filter:
1. `StoriesContent` gets `activity_ids: list[int]` and `slice_ids: list[int]` (empty =
   all, so stored JSON stays valid), plus an `unsliced: bool` flag for stories without a
   slice. Verify first how story/activity/slice ids behave across map revisions
   (`ActivityEntity`, `SliceEntity`, `StoryEntity.slice_id` in `entities.py`) and where
   the stories are resolved at render time (`export/chapter_renderers.py`,
   `services/chapter_blocks.py`, `workshop/services/*` map readers); use the same filter
   function for the document view, Word export and review checks.
2. When adding a stories chapter ("Stories" in the + menu and the library dialog) show a
   step with two multi-select filters: "Spalten" (activities of the map) and
   "Umsetzungsschnitte" (slices, plus "Ohne Schnitt"), with counts of matching stories,
   and "Alle" as default. The same two filters sit in the right panel (`panel.py`
   `_type_settings`) and as a compact filter bar in the floating toolbar of the block so
   they can be changed later. Changes go through a handler that saves the content like
   `set_group_by` (`requires_offer_editor`, protected chapters locked).
3. Rendering: only matching stories, groups without stories disappear, header line shows
   the filter ("Aus der Story Map · Spalten: A, B · Schnitt: 1"). Empty result shows the
   existing "keine Stories" note with the active filter. If a filtered activity or slice
   no longer exists in the newest map revision it is dropped from the filter and the
   chapter is flagged "Bitte prüfen" (existing `needs_review`).
4. Tests: filter combinations (activity only, slice only, both, unsliced), old JSON
   without filters, export of a filtered chapter.

### E. Table and image editors behave like Confluence
Table (`blocks/table.py` replaced by a Tiptap table editor, new `table_editor.jsx` sharing
the extension/store setup of `chapter_editor.jsx`):
1. Real table editing with `@tiptap/extension-table` (Table, TableRow, TableHeader,
   TableCell); cells hold inline text only (bold, italic, underline, strike, link, code),
   mapped to `TableContent` (`columns` from the header row, `rows` of `Inline`) by new
   `table_to_html` / `html_to_table` helpers next to `editor_io.py`. Limits from
   `schema.py` (`MAX_COLUMNS`, `MAX_TABLE_ROWS`, `MAX_CELL`) are enforced in the editor
   and again on save with German messages.
2. Floating table toolbar over the selected table/cell (Confluence): insert row above or
   below, insert column left or right, delete row, delete column, delete table (asks
   first, goes through the existing remove flow), plus a hover "+" on the row/column edges
   to add one. Tab / Shift+Tab move between cells, Tab in the last cell adds a row, Enter
   stays in the cell, cell selection with drag/shift-click. The header row is always on
   (the model requires it); merged cells, column widths and cell colors are not in the
   model and stay out.
3. Shares the one fixed top toolbar for inline formatting of the focused cell text.
Image (`blocks/image.py` + `image_editor.jsx` or a Reflex block):
1. Empty image chapter shows a drop zone: click to pick, drag a file in, or paste from
   the clipboard (same upload handler as D).
2. Selecting the image shows a floating image toolbar: align left/center/right (stored as
   `align`), size presets (klein, mittel, groß, Original = width percent) with drag handles
   on the corners, replace, alt text, delete. The description sits below as an inline
   editable caption.
Both keep the optional description under the block and no headline.

### F. Insert a chapter between two chapters (left side of the document)
1. In the document, the gap between two blocks (and before the first / after the last) has
   a hover "+" in the left margin with a thin line, like Notion/Confluence. Click opens a
   small menu with the chapter types: Text, Tabelle, Bild, Stories, Kalkulation, plus
   "Aus Bibliothek …" (opens the existing library dialog) and, for text, "Unterkapitel".
   Keyboard: the "+" is a focusable button; Enter opens the menu, arrows choose.
2. Same "+" appears between rows in the outline on hover (small, left of the row), using
   the same handler, so both columns offer it.
3. Backend: `add_chapter(after, ...)` in `OutlineService` already inserts after a key;
   handlers take an explicit `after_key` (or "start") instead of `_after()` = active key
   (`states/outline_mixin.py::add_block/add_blank`). Level rule: text/stories/calc join the
   level of the chapter before (or level 1 at the start); table and image are forced to
   level 2 and cannot go to position 0 (menu entry disabled there, with a tooltip). A new
   text chapter gets focus with the cursor in the title.
4. The existing bottom "+ Kapitel einfügen" button stays as the last gap.

## Deliverables
- New also: `table_editor.jsx`, table/html helpers, insert-between menu component
  (`components/chapters/insert_menu.py`).
- Changed: `content/schema.py`, `content/editor_io.py`, `content/text.py`,
  `export/chapter_renderers.py`, `ai/render.py`, `services/outline.py`,
  `services/chapter_document.py`, `states/outline_mixin.py`, `states/chapter_state.py`,
  `components/chapters/{outline,document,editor,dialogs,labels,panel}.py`,
  `components/chapters/blocks/prose.py`, `chapter_editor.jsx`, `assets/css/aq-workshop.css`.
- New: `components/chapters/blocks/image.py`, image route/service, toolbar component.
- Files stay under 1000 lines (`chapter_state.py` and `services/chapters.py` are the
  large ones: put new logic in mixins/services as the repo does, see memory
  "Reflex mixin, not substate").
- Tests first, in `components/alloq-offer/tests/`: `test_workshop_editor_io.py` (every new
  tag round trips, images/tables in text are reported), `test_workshop_chapters.py` and
  outline service tests (add_subchapter, indent/outdent, group move, position 0 stays
  level 1), `test_workshop_chapter_state.py` (focus selects, per-key autosave, editable per
  chapter), export test with the new runs/blocks and an image chapter, schema back-compat
  test with old stored JSON.

## Success criteria
- `task format && task lint && task typecheck && task test` green, coverage >= 80% for
  touched non-Reflex classes and states.
- Visual check with the local app (chrome-devtools browser, see memory
  "Local visual check browser"): click into any text chapter and type without a border
  jump, toolbar acts on the focused chapter, Arrow keys cross chapters, every formatting
  option shows in the editor, in the read view and in the exported .docx.
- Navigation: "+ Unterkapitel" creates a numbered sub chapter (e.g. 2.1), indent/outdent
  and drag keep numbering right, collapsing hides children, outline stays on the left.
- Image chapter: upload (pick, drop, paste), resize/align, caption, export to Word.
- Table chapter: add/remove rows and columns with the floating toolbar, Tab navigation,
  formatted cell text survives save, reload and Word export.
- Text gutter: "+" and grip appear on hover per block, drag moves blocks, menu converts
  them; nested bullets and inline code look like the screenshot.
- Stories chapter: choose columns and slices when adding and later; document, Word export
  and checks show the same filtered stories.
- Hover "+" between two chapters inserts each chapter type at exactly that position;
  table/image are refused at position 0.
- Alembic: if a revision is needed it is hand-written and handed to the user to run.

## Out of scope
- Images or tables inside a text chapter.
- Real-time multi-user editing, comments, mentions, page-wide drag handles.
- A third chapter level.
- Slash menu and bubble menu (single fixed toolbar only); can follow later.
- Changing the right panel layout beyond what the new level/image types need.
