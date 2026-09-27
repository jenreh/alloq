/**
 * ExcelGrid — reusable Excel-like selection, navigation, editing and
 * clipboard for any Reflex-rendered numeric grid.
 *
 * The children render the grid (any markup). Editable rows carry
 *   data-row-key="<unique row key>" data-block="<group key, optional>"
 * and editable cells inside them carry
 *   data-cell-key="<unique cell key>" data-col="<column key>" data-value="<number>".
 * Rows of the same block form one "data region" for Ctrl+Arrow and Ctrl+A.
 * Everything interactive happens in the browser; only committed batches are
 * sent to the server through `onCommit([{key, value}])`. Invalid pasted cells
 * are reported through `onReject(count)`.
 *
 * While `dirty` is true, leaving the route (links, redirects, Back) is held
 * by a React Router blocker and the user can stay, discard or save & leave;
 * closing/reloading the tab triggers the browser's beforeunload prompt.
 */
import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Button, Group, Modal, Text } from "@mantine/core";
import { useBlocker } from "react-router";
import * as G from "./grid_logic.js";

const FOCUS_RING = "inset 0 0 0 2px var(--mantine-color-blue-6)";
const RANGE_FILL = "inset 0 0 0 999px light-dark(rgba(34, 139, 230, 0.14), rgba(34, 139, 230, 0.24))";
const ROW_PX = 32;

function readLayout(root) {
  const rows = [];
  const els = new Map();
  let cols = [];
  root.querySelectorAll("[data-row-key]").forEach((rowEl) => {
    const cells = [];
    rowEl.querySelectorAll("[data-cell-key]").forEach((el) => {
      const key = el.getAttribute("data-cell-key");
      cells.push(key);
      els.set(key, el);
    });
    if (cells.length) {
      if (!rows.length) cols = cells.map((k) => els.get(k).getAttribute("data-col") || "");
      rows.push({
        key: rowEl.getAttribute("data-row-key"),
        block: rowEl.getAttribute("data-block") || "",
        cells,
      });
    }
  });
  return { rows, els, cols };
}

function attr(value) {
  return String(value).replace(/["\\]/g, "\\$&");
}

function selectionCss(id, layout, sel) {
  // Column keys come from data-col on the cells of the first row.
  if (!sel.focusKey || !layout.rows.length) return "";
  const root = `#${CSS.escape(id)}`;
  const focusRule = `${root} [data-cell-key="${attr(sel.focusKey)}"]{box-shadow:${FOCUS_RING};}`;
  const a = G.findPos(layout, sel.anchorKey);
  const f = G.findPos(layout, sel.focusKey);
  if (!a || !f || (a.r === f.r && a.c === f.c)) return focusRule;
  const rect = G.normalizeRange(a, f);
  const rowSel = [];
  for (let r = rect.r0; r <= rect.r1; r++) {
    rowSel.push(`[data-row-key="${attr(layout.rows[r].key)}"]`);
  }
  const colSel = [];
  for (let c = rect.c0; c <= rect.c1; c++) {
    colSel.push(`[data-col="${attr(layout.cols[c])}"]`);
  }
  const rangeRule = `${root} :is(${rowSel.join(",")}) :is(${colSel.join(",")}){box-shadow:${RANGE_FILL};}`;
  const focusInRange = `${root} [data-cell-key="${attr(sel.focusKey)}"]{box-shadow:${FOCUS_RING};}`;
  return rangeRule + focusInRange;
}

function scrollIntoViewIfNeeded(root, el) {
  if (!root || !el) return;
  const header = root.querySelector("[data-grid-header]");
  const headerH = header ? header.getBoundingClientRect().height : 0;
  const rowEl = el.closest("[data-row-key]");
  const label = rowEl ? rowEl.firstElementChild : null;
  const labelW = label && label !== el ? label.getBoundingClientRect().width : 0;
  const rr = root.getBoundingClientRect();
  const cr = el.getBoundingClientRect();
  if (cr.bottom > rr.bottom - 2) root.scrollTop += cr.bottom - rr.bottom + 2;
  else if (cr.top < rr.top + headerH) root.scrollTop -= rr.top + headerH - cr.top + 2;
  if (cr.right > rr.right - 2) root.scrollLeft += cr.right - rr.right + 2;
  else if (cr.left < rr.left + labelW) root.scrollLeft -= rr.left + labelW - cr.left + 2;
}

export function ExcelGrid({
  id,
  ref,
  children,
  className,
  onCommit,
  onSave,
  onReject,
  revision,
  dirty,
  gridLabel,
  minValue = 0,
  maxValue,
  decimals = 2,
  decimalSeparator = ",",
  invalidMessage = "Ungültige Zahl",
  saving = false,
  leaveTitle = "Ungespeicherte Änderungen",
  leaveMessage = "Es gibt ungespeicherte Änderungen. Möchtest du die Seite wirklich verlassen?",
  leaveStayLabel = "Bleiben",
  leaveDiscardLabel = "Verwerfen",
  leaveSaveLabel = "Speichern & verlassen",
}) {
  const parseOpts = { min: minValue, max: maxValue ?? Infinity, decimals };
  const formatOpts = { decimals, separator: decimalSeparator };
  const rootRef = useRef(null);
  const inputRef = useRef(null);
  const layoutRef = useRef(null);
  const pendingRef = useRef(new Map());
  const undoRef = useRef([]);
  const redoRef = useRef([]);
  const dragRef = useRef(false);
  const closingRef = useRef(false);
  const [sel, setSel] = useState({ anchorKey: null, focusKey: null, block: null });
  const [editor, setEditor] = useState(null); // {key, value, mode, invalid, box}
  const [layoutVersion, setLayoutVersion] = useState(0);

  // React 19: `ref` arrives as a prop (Reflex passes one when `id` is set).
  const setRootRef = useCallback(
    (node) => {
      rootRef.current = node;
      if (typeof ref === "function") ref(node);
      else if (ref) ref.current = node;
    },
    [ref],
  );

  // --- layout cache -------------------------------------------------------

  const layout = useCallback(() => {
    if (!layoutRef.current && rootRef.current) layoutRef.current = readLayout(rootRef.current);
    return layoutRef.current || { rows: [], els: new Map(), cols: [] };
  }, []);

  const getValue = useCallback(
    (key) => {
      if (pendingRef.current.has(key)) return pendingRef.current.get(key);
      const el = layout().els.get(key);
      return el ? Number(el.getAttribute("data-value")) || 0 : 0;
    },
    [layout],
  );

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return undefined;
    const observer = new MutationObserver((records) => {
      if (records.some((r) => r.type === "childList")) {
        layoutRef.current = null;
        setLayoutVersion((v) => v + 1);
      }
      const pending = pendingRef.current;
      if (pending.size) {
        const els = layout().els;
        for (const [key, value] of pending) {
          const el = els.get(key);
          if (!el || Number(el.getAttribute("data-value")) === value) pending.delete(key);
        }
      }
    });
    observer.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ["data-value"] });
    return () => observer.disconnect();
  }, [layout]);

  useEffect(() => {
    undoRef.current = [];
    redoRef.current = [];
    pendingRef.current.clear();
    layoutRef.current = null;
  }, [revision]);

  useEffect(() => {
    if (!dirty) return undefined;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  // --- in-app navigation guard (links, redirects, Back) -------------------

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      Boolean(dirty) && currentLocation.pathname !== nextLocation.pathname,
  );
  const blocked = blocker.state === "blocked";
  const [leaveSaving, setLeaveSaving] = useState(false);
  const sawSavingRef = useRef(false);

  useEffect(() => {
    if (!blocked) {
      setLeaveSaving(false);
      return;
    }
    if (!dirty) {
      // Saved (or nothing left to lose) while the dialog was open.
      blocker.proceed();
    } else if (leaveSaving) {
      if (saving) sawSavingRef.current = true;
      else if (sawSavingRef.current) {
        // Save finished but changes remain (error) — let the user decide again.
        sawSavingRef.current = false;
        setLeaveSaving(false);
      }
    }
  }, [blocked, dirty, saving, leaveSaving, blocker]);

  const stay = () => blocker.reset?.();
  const discard = () => blocker.proceed?.();
  const saveAndLeave = () => {
    sawSavingRef.current = false;
    setLeaveSaving(true);
    onSave?.();
  };

  // --- selection helpers --------------------------------------------------

  const current = useCallback(() => {
    const lay = layout();
    const focus = G.resolvePos(lay, sel.focusKey, sel.block);
    if (!focus) return null;
    const anchor = G.findPos(lay, sel.anchorKey) || focus;
    return { lay, focus, anchor, rect: G.normalizeRange(anchor, focus) };
  }, [layout, sel]);

  const select = useCallback((lay, focus, anchor = focus) => {
    const focusKey = G.keyAt(lay, focus);
    const anchorKey = G.keyAt(lay, anchor);
    setSel({ anchorKey, focusKey, block: lay.rows[focus.r].block });
  }, []);

  const selectRect = useCallback(
    (lay, rect) => select(lay, { r: rect.r1, c: rect.c1 }, { r: rect.r0, c: rect.c0 }),
    [select],
  );

  useLayoutEffect(() => {
    if (!sel.focusKey) return;
    scrollIntoViewIfNeeded(rootRef.current, layout().els.get(sel.focusKey));
  }, [sel.focusKey, layout]);

  const focusRoot = useCallback(() => {
    rootRef.current?.focus({ preventScroll: true });
  }, []);

  // --- committing ---------------------------------------------------------

  const applyChanges = useCallback(
    (changes, { record = true } = {}) => {
      const batch = G.withBefore(changes, getValue);
      if (!batch.length) return;
      for (const ch of batch) pendingRef.current.set(ch.key, ch.after);
      onCommit?.(batch.map((ch) => ({ key: ch.key, value: ch.after })));
      if (record) {
        undoRef.current.push(batch);
        if (undoRef.current.length > 200) undoRef.current.shift();
        redoRef.current = [];
      }
    },
    [getValue, onCommit],
  );

  const history = useCallback(
    (from, to, field) => {
      const batch = from.current.pop();
      if (!batch) return;
      applyChanges(
        batch.map((ch) => ({ key: ch.key, value: ch[field] })),
        { record: false },
      );
      to.current.push(batch);
      const lay = layout();
      const positions = batch.map((ch) => G.findPos(lay, ch.key)).filter(Boolean);
      if (positions.length) selectRect(lay, G.boundingRect(positions));
    },
    [applyChanges, layout, selectRect],
  );

  // --- editor -------------------------------------------------------------

  const startEdit = useCallback(
    (mode, initial) => {
      const cur = current();
      if (!cur) return;
      const key = G.keyAt(cur.lay, cur.focus);
      const el = cur.lay.els.get(key);
      const root = rootRef.current;
      if (!el || !root) return;
      scrollIntoViewIfNeeded(root, el);
      const rr = root.getBoundingClientRect();
      const cr = el.getBoundingClientRect();
      const box = {
        top: cr.top - rr.top + root.scrollTop - root.clientTop,
        left: cr.left - rr.left + root.scrollLeft - root.clientLeft,
        width: cr.width,
        height: cr.height,
      };
      const value = initial ?? G.formatNumber(getValue(key), formatOpts);
      setSel({ anchorKey: key, focusKey: key, block: cur.lay.rows[cur.focus.r].block });
      setEditor({ key, value, mode, invalid: false, box });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [current, getValue, decimals, decimalSeparator],
  );

  useLayoutEffect(() => {
    const input = inputRef.current;
    if (!editor || !input || document.activeElement === input) return;
    input.focus({ preventScroll: true });
    const end = input.value.length;
    input.setSelectionRange(end, end);
  }, [editor]);

  const closeEditor = useCallback(() => {
    closingRef.current = true;
    setEditor(null);
    focusRoot();
    setTimeout(() => {
      closingRef.current = false;
    }, 0);
  }, [focusRoot]);

  /** Commit the editor; returns false (and keeps it open) when invalid. */
  const commitEditor = useCallback(
    (then) => {
      if (!editor) return true;
      const value = G.parseNumber(editor.value, parseOpts);
      if (value === null) {
        setEditor({ ...editor, invalid: true });
        return false;
      }
      applyChanges([{ key: editor.key, value }]);
      closeEditor();
      if (then) then();
      return true;
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [editor, applyChanges, closeEditor, minValue, maxValue, decimals],
  );

  const moveBy = useCallback(
    (fn) => {
      const lay = layout();
      const focus = G.resolvePos(lay, sel.focusKey, sel.block);
      if (focus) select(lay, fn(lay, focus));
    },
    [layout, sel, select],
  );

  const onEditorKeyDown = (e) => {
    e.stopPropagation();
    if (e.nativeEvent.isComposing) return;
    const arrows = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right" };
    if (e.key === "Enter") {
      e.preventDefault();
      commitEditor(() => moveBy((lay, p) => G.move(lay, p, e.shiftKey ? "up" : "down")));
    } else if (e.key === "Tab") {
      e.preventDefault();
      commitEditor(() => moveBy((lay, p) => G.tabMove(lay, p, e.shiftKey)));
    } else if (e.key === "Escape") {
      e.preventDefault();
      closeEditor();
    } else if (e.key === "F2") {
      e.preventDefault();
      setEditor({ ...editor, mode: editor.mode === "edit" ? "enter" : "edit" });
    } else if (arrows[e.key] && editor.mode === "enter") {
      e.preventDefault();
      commitEditor(() => moveBy((lay, p) => G.move(lay, p, arrows[e.key])));
    }
  };

  const onEditorBlur = () => {
    if (closingRef.current || !editor) return;
    if (!commitEditor()) closeEditor();
  };

  // --- keyboard (selection mode) -----------------------------------------

  const onKeyDown = (e) => {
    if (e.target !== rootRef.current || e.nativeEvent.isComposing) return;
    const cur = current();
    if (!cur) return;
    const { lay, focus, anchor, rect } = cur;
    const mod = e.ctrlKey || e.metaKey;
    const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    const arrows = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right" };
    let handled = true;

    if (arrows[key] || key === "Home" || key === "End") {
      const dir = arrows[key] || key.toLowerCase();
      const next = G.move(lay, focus, dir, { ctrl: mod });
      select(lay, next, e.shiftKey ? anchor : next);
    } else if (key === "PageDown" || key === "PageUp") {
      const rows = Math.floor((rootRef.current.clientHeight || ROW_PX) / ROW_PX) - 4;
      const next = G.pageMove(lay, focus, rows, key === "PageUp");
      select(lay, next, e.shiftKey ? anchor : next);
    } else if (key === "Tab") {
      select(lay, G.tabMove(lay, focus, e.shiftKey));
    } else if (key === "Enter" && !mod) {
      select(lay, G.move(lay, focus, e.shiftKey ? "up" : "down"));
    } else if (key === "F2") {
      startEdit("edit");
    } else if (key === "Delete" || key === "Backspace") {
      applyChanges(G.planClear(lay, rect));
    } else if (key === "Escape") {
      select(lay, focus);
    } else if (mod && key === "a") {
      const block = G.blockRect(lay, focus.r);
      const same = ["r0", "r1", "c0", "c1"].every((k) => block[k] === rect[k]);
      selectRect(lay, same ? G.allRect(lay) : block);
    } else if (mod && (key === "y" || (key === "z" && e.shiftKey))) {
      history(redoRef, undoRef, "after");
    } else if (mod && key === "z") {
      history(undoRef, redoRef, "before");
    } else if (mod && (key === "d" || key === "r")) {
      applyChanges(G.planFill(lay, rect, key === "d" ? "down" : "right", getValue));
    } else if (mod && key === "s") {
      onSave?.();
    } else if (mod && (key === "c" || key === "x" || key === "v")) {
      handled = false; // handled by the native clipboard events below
    } else if (e.key.length === 1 && !mod && !e.altKey) {
      startEdit("enter", e.key);
    } else {
      handled = false;
    }
    if (handled) e.preventDefault();
  };

  // --- clipboard (native events; no permission prompt) --------------------

  useEffect(() => {
    const isActive = () => document.activeElement === rootRef.current;
    const copy = (e, cut) => {
      if (!isActive()) return;
      const cur = current();
      if (!cur) return;
      const matrix = [];
      for (let r = cur.rect.r0; r <= cur.rect.r1; r++) {
        const row = [];
        for (let c = cur.rect.c0; c <= cur.rect.c1; c++) row.push(getValue(G.keyAt(cur.lay, { r, c })));
        matrix.push(row);
      }
      e.clipboardData.setData("text/plain", G.toTSV(matrix, formatOpts));
      e.preventDefault();
      if (cut) applyChanges(G.planClear(cur.lay, cur.rect));
    };
    const onCopy = (e) => copy(e, false);
    const onCut = (e) => copy(e, true);
    const onPaste = (e) => {
      if (!isActive()) return;
      const cur = current();
      if (!cur) return;
      e.preventDefault();
      const matrix = G.parseTSV(e.clipboardData.getData("text/plain"));
      const plan = G.planPaste(cur.lay, cur.rect, matrix, parseOpts);
      applyChanges(plan.changes);
      selectRect(cur.lay, plan.rect);
      if (plan.skipped) onReject?.(plan.skipped);
    };
    document.addEventListener("copy", onCopy);
    document.addEventListener("cut", onCut);
    document.addEventListener("paste", onPaste);
    return () => {
      document.removeEventListener("copy", onCopy);
      document.removeEventListener("cut", onCut);
      document.removeEventListener("paste", onPaste);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, getValue, applyChanges, selectRect, onReject, minValue, maxValue, decimals, decimalSeparator]);

  // --- mouse --------------------------------------------------------------

  const cellFromEvent = (e) => {
    if (e.target.closest("button, a, input, [role='button']")) return null;
    const el = e.target.closest("[data-cell-key]");
    return el && rootRef.current?.contains(el) ? el.getAttribute("data-cell-key") : null;
  };

  const onMouseDown = (e) => {
    if (e.button !== 0) return;
    const key = cellFromEvent(e);
    if (!key) return;
    e.preventDefault();
    if (editor) {
      if (editor.key === key) return;
      if (!commitEditor()) closeEditor();
    }
    focusRoot();
    const lay = layout();
    const pos = G.findPos(lay, key);
    if (!pos) return;
    const anchor = e.shiftKey ? G.findPos(lay, sel.anchorKey) || pos : pos;
    select(lay, pos, anchor);
    dragRef.current = true;
  };

  const onMouseOver = (e) => {
    if (!dragRef.current) return;
    const key = cellFromEvent(e);
    if (!key || key === sel.focusKey) return;
    const lay = layout();
    const pos = G.findPos(lay, key);
    const anchor = G.findPos(lay, sel.anchorKey);
    if (pos && anchor) select(lay, pos, anchor);
  };

  useEffect(() => {
    const up = () => {
      dragRef.current = false;
    };
    window.addEventListener("mouseup", up);
    return () => window.removeEventListener("mouseup", up);
  }, []);

  const onDoubleClick = (e) => {
    const key = cellFromEvent(e);
    if (key) startEdit("edit");
  };

  const onFocus = (e) => {
    if (e.target !== rootRef.current || sel.focusKey) return;
    const lay = layout();
    if (lay.rows.length) select(lay, { r: 0, c: 0 });
  };

  // --- render -------------------------------------------------------------

  void layoutVersion; // re-render selection CSS after DOM changes
  const css = id ? selectionCss(id, layout(), sel) : "";

  return (
    <div
      id={id}
      ref={setRootRef}
      className={className}
      tabIndex={0}
      role="grid"
      aria-label={gridLabel}
      onKeyDown={onKeyDown}
      onMouseDown={onMouseDown}
      onMouseOver={onMouseOver}
      onDoubleClick={onDoubleClick}
      onFocus={onFocus}
    >
      <style>{css}</style>
      {children}
      <Modal
        opened={blocked}
        onClose={stay}
        title={leaveTitle}
        centered
        zIndex={400}
        overlayProps={{ backgroundOpacity: 0.5, blur: 4 }}
      >
        <Text size="sm">{leaveMessage}</Text>
        <Group justify="flex-end" mt="lg" gap="sm">
          <Button variant="default" onClick={stay} data-autofocus>
            {leaveStayLabel}
          </Button>
          <Button variant="light" color="red" onClick={discard} disabled={leaveSaving}>
            {leaveDiscardLabel}
          </Button>
          {onSave && (
            <Button onClick={saveAndLeave} loading={leaveSaving}>
              {leaveSaveLabel}
            </Button>
          )}
        </Group>
      </Modal>
      {editor && (
        <input
          ref={inputRef}
          className="grid-editor"
          value={editor.value}
          aria-invalid={editor.invalid}
          title={editor.invalid ? invalidMessage : undefined}
          onChange={(e) => setEditor({ ...editor, value: e.target.value, invalid: false })}
          onKeyDown={onEditorKeyDown}
          onBlur={onEditorBlur}
          style={{
            position: "absolute",
            top: editor.box.top,
            left: editor.box.left,
            width: editor.box.width,
            height: editor.box.height,
            zIndex: 20,
            boxSizing: "border-box",
            padding: "0 4px",
            textAlign: "center",
            fontSize: "0.8125rem",
            fontVariantNumeric: "tabular-nums",
            border: `2px solid var(--mantine-color-${editor.invalid ? "red" : "blue"}-6)`,
            borderRadius: 0,
            outline: "none",
            backgroundColor: "var(--alloq-surface-solid)",
            color: "var(--alloq-text)",
          }}
        />
      )}
    </div>
  );
}
