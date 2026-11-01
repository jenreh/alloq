import React, { useCallback, useEffect, useRef, useState } from "react";
import { useEditor, useEditorState } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Document from "@tiptap/extension-document";
import { Table, TableCell, TableHeader, TableRow } from "@tiptap/extension-table";
import { CellSelection, cellAround } from "@tiptap/pm/tables";
import { TextSelection } from "@tiptap/pm/state";
import { RichTextEditor } from "@mantine/tiptap";
import { Plus, Trash2 } from "lucide-react";
import { clearFocused, setFocused } from "./chapter_editor.jsx";

const LINK = /^(https?:\/\/|mailto:)/i;
// How close to a row or column line the pointer must be for its "+".
const NEAR = 8;

// A table chapter: one table, a header row, cells of plain paragraphs; the one
// toolbar of the page formats the cell text.
function extensions() {
  return [
    StarterKit.configure({
      document: false,
      heading: false,
      blockquote: false,
      bulletList: false,
      orderedList: false,
      listItem: false,
      listKeymap: false,
      codeBlock: false,
      horizontalRule: false,
      trailingNode: false,
      link: {
        openOnClick: false,
        autolink: true,
        protocols: ["mailto"],
        isAllowedUri: (url, ctx) => ctx.defaultValidate(url) && LINK.test(url),
      },
    }),
    Document.extend({ content: "table" }),
    Table.configure({ resizable: false, allowTableNodeSelection: false }),
    TableRow,
    TableHeader.extend({ content: "paragraph" }),
    TableCell.extend({ content: "paragraph" }),
  ];
}

function shape(editor) {
  const table = editor?.state.doc.firstChild;
  if (!table || table.type.name !== "table") {
    return { rows: 0, columns: 0 };
  }
  return { rows: table.childCount, columns: table.firstChild?.childCount || 0 };
}

// Cell boxes relative to the frame, for the handles and the "+" markers.
function measure(frame) {
  const table = frame?.querySelector("table");
  if (!table) {
    return null;
  }
  const base = frame.getBoundingClientRect();
  const box = table.getBoundingClientRect();
  const rows = Array.from(table.rows);
  return {
    left: box.left - base.left,
    top: box.top - base.top,
    width: box.width,
    height: box.height,
    columns: Array.from(rows[0]?.cells || []).map((cell) => {
      const r = cell.getBoundingClientRect();
      return { left: r.left - base.left, width: r.width };
    }),
    rows: rows.map((row) => {
      const r = row.getBoundingClientRect();
      return { top: r.top - base.top, height: r.height };
    }),
  };
}

function cellPos(editor, row, column) {
  const table = editor.view.dom.querySelector("table");
  const cell = table?.rows[row]?.cells[column];
  return cell ? editor.view.posAtDOM(cell, 0) : null;
}

function selectLine(editor, row, column, whole) {
  const pos = cellPos(editor, row, column);
  if (pos == null) {
    return;
  }
  const $cell = cellAround(editor.state.doc.resolve(pos));
  if (!$cell) {
    return;
  }
  const selection =
    whole === "row" ? CellSelection.rowSelection($cell) : CellSelection.colSelection($cell);
  editor.view.dispatch(editor.state.tr.setSelection(selection));
  editor.view.focus();
}

function insertAt(editor, row, column, command) {
  const pos = cellPos(editor, row, column);
  if (pos == null) {
    return;
  }
  editor
    .chain()
    .focus()
    .command(({ tr }) => {
      tr.setSelection(TextSelection.near(tr.doc.resolve(pos)));
      return true;
    })
    [command]()
    .run();
}

export function TableEditor({
  content = "",
  editable = true,
  labels = {},
  maxColumns = 8,
  contentClassName,
  onUpdate,
  onBlur,
  onFocus,
  onRemove,
  children,
}) {
  const frame = useRef(null);
  const [layout, setLayout] = useState(null);
  const [hover, setHover] = useState(null);
  const [active, setActive] = useState(false);

  const editor = useEditor({
    extensions: extensions(),
    content,
    editable,
    // Only a table can be saved; a deleted table is not sent.
    onUpdate: ({ editor: current }) =>
      onUpdate && shape(current).rows > 0 && onUpdate(current.getHTML()),
    onBlur: ({ editor: current }) => {
      setActive(false);
      if (onBlur && shape(current).rows > 0) {
        onBlur(current.getHTML());
      }
    },
    onFocus: ({ editor: current }) => {
      setActive(true);
      setFocused(current);
      if (onFocus) {
        onFocus();
      }
    },
  });
  const size = useEditorState({ editor, selector: (state) => shape(state.editor) });

  const relayout = useCallback(() => setLayout(measure(frame.current)), []);

  useEffect(() => {
    if (!editor) {
      return undefined;
    }
    relayout();
    editor.on("update", relayout);
    const observer = new ResizeObserver(relayout);
    observer.observe(frame.current);
    return () => {
      editor.off("update", relayout);
      observer.disconnect();
    };
  }, [editor, relayout]);

  useEffect(() => {
    if (!editor || editor.isDestroyed || editor.isFocused) {
      return;
    }
    if (content !== editor.getHTML()) {
      editor.commands.setContent(content, { emitUpdate: false });
    }
  }, [content, editor]);

  useEffect(() => {
    if (editor && editor.isEditable !== editable) {
      editor.setEditable(editable);
    }
  }, [editable, editor]);

  useEffect(() => () => clearFocused(editor), [editor]);

  if (!editor) {
    return null;
  }

  const full = size.columns >= maxColumns;
  const onlyRow = size.rows <= 1;
  const onlyColumn = size.columns <= 1;

  // The line nearest to the pointer above the table (columns) or left of it (rows).
  const onMove = (event) => {
    if (!editable || !layout) {
      return;
    }
    const base = frame.current.getBoundingClientRect();
    const x = event.clientX - base.left;
    const y = event.clientY - base.top;
    if (y < layout.top && !full) {
      const lines = layout.columns.map((c) => c.left + c.width);
      const index = lines.findIndex((line) => Math.abs(line - x) <= NEAR);
      setHover(index >= 0 ? { kind: "column", index, at: lines[index] } : null);
    } else if (x < layout.left) {
      const lines = layout.rows.map((r) => r.top + r.height);
      const index = lines.findIndex((line) => Math.abs(line - y) <= NEAR);
      setHover(index >= 0 ? { kind: "row", index, at: lines[index] } : null);
    } else {
      setHover(null);
    }
  };

  const insertHere = () => {
    if (hover?.kind === "column") {
      insertAt(editor, 0, hover.index, "addColumnAfter");
    } else if (hover?.kind === "row") {
      insertAt(editor, hover.index, 0, "addRowAfter");
    }
    setHover(null);
  };

  return (
    <RichTextEditor
      editor={editor}
      variant="subtle"
      withTypographyStyles={false}
      labels={labels}
      classNames={{ root: "aq-doc-editor aq-doc-table-editor", content: contentClassName }}
    >
      <div
        ref={frame}
        className="aq-doc-table-frame"
        data-active={active ? "true" : "false"}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        {editable && active && (
          // Confluence: the table toolbar floats above the table while the
          // cursor is in it. Mouse down keeps the cursor in the cell.
          <div
            className="aq-doc-table-toolbar"
            role="toolbar"
            aria-label={labels.tableToolbarLabel}
            onMouseDown={(event) => event.preventDefault()}
          >
            <RichTextEditor.ControlsGroup>
              <RichTextEditor.TableRowBefore />
              <RichTextEditor.TableRowAfter />
              <RichTextEditor.TableRowDelete disabled={onlyRow} />
            </RichTextEditor.ControlsGroup>
            <RichTextEditor.ControlsGroup>
              <RichTextEditor.TableColumnBefore disabled={full} />
              <RichTextEditor.TableColumnAfter disabled={full} />
              <RichTextEditor.TableColumnDelete disabled={onlyColumn} />
            </RichTextEditor.ControlsGroup>
            {children}
            {onRemove && (
              <RichTextEditor.Control
                aria-label={labels.tableRemoveLabel}
                title={labels.tableRemoveLabel}
                onClick={() => onRemove()}
              >
                <Trash2 size={16} />
              </RichTextEditor.Control>
            )}
          </div>
        )}
        {editable && layout && (
          <>
            {layout.columns.map((column, index) => (
              <button
                key={`c${index}`}
                type="button"
                className="aq-doc-table-handle"
                data-kind="column"
                aria-label={labels.selectColumnLabel}
                style={{ left: column.left, top: layout.top - 14, width: column.width }}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectLine(editor, 0, index, "column")}
              />
            ))}
            {layout.rows.map((row, index) => (
              <button
                key={`r${index}`}
                type="button"
                className="aq-doc-table-handle"
                data-kind="row"
                aria-label={labels.selectRowLabel}
                style={{ top: row.top, left: layout.left - 14, height: row.height }}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectLine(editor, index, 0, "row")}
              />
            ))}
          </>
        )}
        {hover && layout && (
          <>
            <span
              className="aq-doc-table-line"
              data-kind={hover.kind}
              style={
                hover.kind === "column"
                  ? { left: hover.at - 1, top: layout.top, height: layout.height }
                  : { top: hover.at - 1, left: layout.left, width: layout.width }
              }
            />
            <button
              type="button"
              className="aq-doc-table-plus"
              aria-label={
                hover.kind === "column" ? labels.addColumnLabel : labels.addRowLabel
              }
              style={
                hover.kind === "column"
                  ? { left: hover.at - 9, top: layout.top - 26 }
                  : { top: hover.at - 9, left: layout.left - 26 }
              }
              onMouseDown={(event) => event.preventDefault()}
              onClick={insertHere}
            >
              <Plus size={12} />
            </button>
          </>
        )}
        <RichTextEditor.Content />
      </div>
    </RichTextEditor>
  );
}
