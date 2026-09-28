/**
 * grid_logic.js — pure, DOM-free helpers for the reusable ExcelGrid component.
 *
 * Layout model (built from the DOM by GridController):
 *   { rows: [{ key, block, cells: [cellKey, ...] }, ...] }
 * Every row has the same number of cells (one per week column).
 * Positions are { r, c } indices into that layout.
 * Ranges are { anchor: {r, c}, focus: {r, c} }.
 */

export function colCount(layout) {
  return layout.rows.length ? layout.rows[0].cells.length : 0;
}

export function clampPos(layout, pos) {
  const nr = layout.rows.length;
  const nc = colCount(layout);
  if (!nr || !nc) return null;
  return {
    r: Math.min(Math.max(pos.r, 0), nr - 1),
    c: Math.min(Math.max(pos.c, 0), nc - 1),
  };
}

export function keyAt(layout, pos) {
  const row = layout.rows[pos.r];
  return row ? row.cells[pos.c] : undefined;
}

export function findPos(layout, key) {
  for (let r = 0; r < layout.rows.length; r++) {
    const c = layout.rows[r].cells.indexOf(key);
    if (c !== -1) return { r, c };
  }
  return null;
}

/** First/last row index of the resource block containing row r. */
export function blockBounds(layout, r) {
  const block = layout.rows[r].block;
  let start = r;
  let end = r;
  while (start > 0 && layout.rows[start - 1].block === block) start--;
  while (end < layout.rows.length - 1 && layout.rows[end + 1].block === block) end++;
  return [start, end];
}

/**
 * Resolve a (possibly stale) key to a position. Falls back to the first row
 * of the same block (key prefix "block|..." is not assumed — the caller passes
 * the block it remembered), then to the first cell.
 */
export function resolvePos(layout, key, block) {
  if (!layout.rows.length || !colCount(layout)) return null;
  const hit = key ? findPos(layout, key) : null;
  if (hit) return hit;
  if (block) {
    const r = layout.rows.findIndex((row) => row.block === block);
    if (r !== -1) return { r, c: 0 };
  }
  return { r: 0, c: 0 };
}

/**
 * Move a position. dir: up | down | left | right | home | end.
 * ctrl: Excel "data region" jumps — each resource block is one region.
 */
export function move(layout, pos, dir, { ctrl = false } = {}) {
  const nr = layout.rows.length;
  const nc = colCount(layout);
  if (!nr || !nc) return pos;
  let { r, c } = pos;
  switch (dir) {
    case "up":
      if (!ctrl) r -= 1;
      else {
        const [start] = blockBounds(layout, r);
        r = r > start ? start : start > 0 ? blockBounds(layout, start - 1)[0] : 0;
      }
      break;
    case "down":
      if (!ctrl) r += 1;
      else {
        const [, end] = blockBounds(layout, r);
        r = r < end ? end : end < nr - 1 ? blockBounds(layout, end + 1)[1] : nr - 1;
      }
      break;
    case "left":
      c = ctrl ? 0 : c - 1;
      break;
    case "right":
      c = ctrl ? nc - 1 : c + 1;
      break;
    case "home":
      c = 0;
      if (ctrl) r = 0;
      break;
    case "end":
      c = nc - 1;
      if (ctrl) r = nr - 1;
      break;
    default:
      break;
  }
  return clampPos(layout, { r, c });
}

/** Tab / Shift+Tab: move right/left, wrapping to the next/previous row. */
export function tabMove(layout, pos, backwards = false) {
  const nr = layout.rows.length;
  const nc = colCount(layout);
  if (!nr || !nc) return pos;
  let idx = pos.r * nc + pos.c + (backwards ? -1 : 1);
  idx = Math.min(Math.max(idx, 0), nr * nc - 1);
  return { r: Math.floor(idx / nc), c: idx % nc };
}

export function pageMove(layout, pos, rowsPerPage, up = false) {
  const step = Math.max(1, rowsPerPage);
  return clampPos(layout, { r: pos.r + (up ? -step : step), c: pos.c });
}

export function normalizeRange(anchor, focus) {
  return {
    r0: Math.min(anchor.r, focus.r),
    r1: Math.max(anchor.r, focus.r),
    c0: Math.min(anchor.c, focus.c),
    c1: Math.max(anchor.c, focus.c),
  };
}

export function boundingRect(positions) {
  return {
    r0: Math.min(...positions.map((p) => p.r)),
    r1: Math.max(...positions.map((p) => p.r)),
    c0: Math.min(...positions.map((p) => p.c)),
    c1: Math.max(...positions.map((p) => p.c)),
  };
}

export function rangeKeys(layout, rect) {
  const keys = [];
  for (let r = rect.r0; r <= rect.r1; r++) {
    for (let c = rect.c0; c <= rect.c1; c++) {
      const k = keyAt(layout, { r, c });
      if (k !== undefined) keys.push(k);
    }
  }
  return keys;
}

/** Rect covering the whole block of row r (Ctrl+A first press). */
export function blockRect(layout, r) {
  const [r0, r1] = blockBounds(layout, r);
  return { r0, r1, c0: 0, c1: colCount(layout) - 1 };
}

export function allRect(layout) {
  return { r0: 0, r1: layout.rows.length - 1, c0: 0, c1: colCount(layout) - 1 };
}

// ---------------------------------------------------------------------------
// Numbers
// ---------------------------------------------------------------------------

/**
 * Parse user/clipboard text as a number within [min, max], rounded to
 * `decimals`. Accepts "1,5", "1.5", "1.234,5", "1,234.5" and a leading "-"
 * when min < 0. Empty → 0. Invalid or out of range → null.
 */
export function parseNumber(text, { min = 0, max = Infinity, decimals = 2 } = {}) {
  let s = String(text ?? "").replace(/[\s ]/g, "");
  if (s === "") return 0;
  const lastComma = s.lastIndexOf(",");
  const lastDot = s.lastIndexOf(".");
  if (lastComma !== -1 && lastDot !== -1) {
    const dec = lastComma > lastDot ? "," : ".";
    const thou = dec === "," ? "." : ",";
    s = s.split(thou).join("").replace(dec, ".");
  } else if (lastComma !== -1) {
    s = s.replace(",", ".");
  }
  if (!/^-?(\d*\.?\d+|\d+\.)$/.test(s)) return null;
  const factor = 10 ** decimals;
  const v = Math.round(Number(s) * factor) / factor;
  if (!Number.isFinite(v) || v < min || v > max) return null;
  return v === 0 ? 0 : v;
}

/** Display/copy format (default: German comma); 0 becomes an empty string. */
export function formatNumber(value, { decimals = 2, separator = "," } = {}) {
  const v = Number(value) || 0;
  if (v === 0) return "";
  const factor = 10 ** decimals;
  return String(Math.round(v * factor) / factor).replace(".", separator);
}

// ---------------------------------------------------------------------------
// Clipboard
// ---------------------------------------------------------------------------

export function toTSV(matrix, formatOptions) {
  return matrix
    .map((row) => row.map((v) => formatNumber(v, formatOptions)).join("\t"))
    .join("\n");
}

export function parseTSV(text) {
  const lines = String(text ?? "").replace(/\r\n?/g, "\n").split("\n");
  while (lines.length && lines[lines.length - 1] === "") lines.pop();
  return lines.map((line) => line.split("\t"));
}

/**
 * Plan a paste of a string matrix onto the layout.
 * - 1×1 source onto a larger selection fills the selection.
 * - A selection that is an exact multiple of the source tiles it.
 * - Otherwise the source is pasted from the selection's top-left, clipped.
 * Returns { changes: [{key, value}], skipped, rect }.
 */
export function planPaste(layout, rect, matrix, parseOptions) {
  const nr = layout.rows.length;
  const nc = colCount(layout);
  const mh = matrix.length;
  const mw = mh ? Math.max(...matrix.map((row) => row.length)) : 0;
  if (!mh || !mw || !nr || !nc) return { changes: [], skipped: 0, rect };
  const selH = rect.r1 - rect.r0 + 1;
  const selW = rect.c1 - rect.c0 + 1;
  const tiles = selH % mh === 0 && selW % mw === 0 && (selH > mh || selW > mw);
  const h = tiles ? selH : mh;
  const w = tiles ? selW : mw;
  const target = {
    r0: rect.r0,
    c0: rect.c0,
    r1: Math.min(rect.r0 + h - 1, nr - 1),
    c1: Math.min(rect.c0 + w - 1, nc - 1),
  };
  const changes = [];
  let skipped = 0;
  for (let r = target.r0; r <= target.r1; r++) {
    for (let c = target.c0; c <= target.c1; c++) {
      const raw = matrix[(r - rect.r0) % mh][(c - rect.c0) % mw];
      // A short (ragged) source row has no cell here: leave the target as is.
      // Only an explicit empty string clears a cell.
      if (raw === undefined) continue;
      const value = parseNumber(raw, parseOptions);
      if (value === null) {
        skipped++;
        continue;
      }
      changes.push({ key: keyAt(layout, { r, c }), value });
    }
  }
  return { changes, skipped, rect: target };
}

/** Ctrl+D (down) / Ctrl+R (right): copy first row/column across the rect. */
export function planFill(layout, rect, direction, getValue) {
  const changes = [];
  for (let r = rect.r0; r <= rect.r1; r++) {
    for (let c = rect.c0; c <= rect.c1; c++) {
      const isSource = direction === "down" ? r === rect.r0 : c === rect.c0;
      if (isSource) continue;
      const src =
        direction === "down"
          ? keyAt(layout, { r: rect.r0, c })
          : keyAt(layout, { r, c: rect.c0 });
      changes.push({ key: keyAt(layout, { r, c }), value: getValue(src) });
    }
  }
  return changes;
}

/**
 * Fill-handle drag: extend `rect` towards `pos` along the dominant axis
 * (vertical wins ties). Returns null while `pos` is inside the rect.
 */
export function fillHandleRect(rect, pos) {
  const vertical = Math.max(pos.r - rect.r1, rect.r0 - pos.r, 0);
  const horizontal = Math.max(pos.c - rect.c1, rect.c0 - pos.c, 0);
  if (!vertical && !horizontal) return null;
  if (vertical >= horizontal) {
    return { ...rect, r0: Math.min(rect.r0, pos.r), r1: Math.max(rect.r1, pos.r) };
  }
  return { ...rect, c0: Math.min(rect.c0, pos.c), c1: Math.max(rect.c1, pos.c) };
}

const mod = (n, m) => ((n % m) + m) % m;

/** Fill handle: repeat the source rect's values across the rest of `target`. */
export function planFillHandle(layout, src, target, getValue) {
  const h = src.r1 - src.r0 + 1;
  const w = src.c1 - src.c0 + 1;
  const changes = [];
  for (let r = target.r0; r <= target.r1; r++) {
    for (let c = target.c0; c <= target.c1; c++) {
      if (r >= src.r0 && r <= src.r1 && c >= src.c0 && c <= src.c1) continue;
      const from = keyAt(layout, { r: src.r0 + mod(r - src.r0, h), c: src.c0 + mod(c - src.c0, w) });
      changes.push({ key: keyAt(layout, { r, c }), value: getValue(from) });
    }
  }
  return changes;
}

export function planClear(layout, rect) {
  return rangeKeys(layout, rect).map((key) => ({ key, value: 0 }));
}

/** Drop no-op changes and attach the previous value for undo. */
export function withBefore(changes, getValue) {
  const out = [];
  for (const ch of changes) {
    const before = getValue(ch.key);
    if (before !== ch.value) out.push({ key: ch.key, before, after: ch.value });
  }
  return out;
}
