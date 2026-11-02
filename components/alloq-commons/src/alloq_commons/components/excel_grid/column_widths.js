/**
 * Pure helpers for resizable grid columns (no React, so node:test can load them).
 *
 * A column's width lives in the CSS variable `--grid-col-<key>` on the grid root;
 * the markup uses `var(--grid-col-<key>, <default>px)` in its grid template.
 */

export const MIN_WIDTH = 120;
export const MAX_WIDTH = 900;

export function columnVar(key) {
  return `--grid-col-${key}`;
}

export function clampWidth(width, min = MIN_WIDTH, max = MAX_WIDTH) {
  return Math.round(Math.min(max, Math.max(min, width)));
}

/** Stored widths by column key; anything unreadable counts as none. */
export function loadWidths(storage, storageKey) {
  if (!storageKey) return {};
  try {
    const data = JSON.parse(storage.getItem(storageKey) || "{}");
    if (!data || typeof data !== "object" || Array.isArray(data)) return {};
    return Object.fromEntries(
      Object.entries(data).filter(([, width]) => Number.isFinite(width)),
    );
  } catch {
    return {};
  }
}

export function saveWidths(storage, storageKey, widths) {
  if (!storageKey) return;
  try {
    storage.setItem(storageKey, JSON.stringify(widths));
  } catch {
    // Private mode or full storage: the widths last for this page only.
  }
}
